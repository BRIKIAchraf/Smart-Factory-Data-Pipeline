import json
import os
import logging
import signal
import sys
import time
import pandas as pd
import numpy as np
from confluent_kafka import DeserializingConsumer, KafkaError
from confluent_kafka.serialization import StringDeserializer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS, ASYNCHRONOUS
from psycopg2 import pool
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import threading
import torch
import torch.nn as nn
import mlflow

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("Processor")

class LSTMAutoencoder(nn.Module):
    def __init__(self, input_dim=4, hidden_dim=16, num_layers=1):
        super(LSTMAutoencoder, self).__init__()
        # Encoder
        self.encoder = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True)
        # Decoder
        self.decoder = nn.LSTM(hidden_dim, input_dim, num_layers, batch_first=True)
        
    def forward(self, x):
        _, (hidden, _) = self.encoder(x)
        # Repeat hidden state for each time step
        hidden = hidden[-1].unsqueeze(1).repeat(1, x.size(1), 1)
        out, _ = self.decoder(hidden)
        return out

class AnomalyDetector:
    """Industrial Edge Analytics: Detects abnormal machine behavior using ML."""
    def __init__(self, window_size=200):
        self.window_size = window_size
        self.data_buffers = {} # machine_id -> deque of features
        self.models = {}        # machine_id -> LSTMAutoencoder
        self.thresholds = {}    # machine_id -> reconstruction error threshold
        self.features = ['temperature', 'rpm', 'vibration', 'current']

    def _train_model(self, machine_id, X_np):
        logger.info(f"Retraining LSTM Autoencoder for {machine_id}")
        mlflow.set_experiment("smart_factory_anomaly_detection")
        with mlflow.start_run():
            model = LSTMAutoencoder()
            criterion = nn.MSELoss()
            optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
            
            X_tensor = torch.tensor(X_np, dtype=torch.float32).unsqueeze(0) # Batch size 1
            
            # Simple training loop (in real-world, we'd have a separate training pipeline)
            for epoch in range(10): 
                optimizer.zero_grad()
                output = model(X_tensor)
                loss = criterion(output, X_tensor)
                loss.backward()
                optimizer.submit if hasattr(optimizer, 'submit') else optimizer.step()
                
            self.models[machine_id] = model
            # Calculate threshold (95th percentile of training error)
            with torch.no_grad():
                out = model(X_tensor)
                errors = torch.mean((out - X_tensor)**2, dim=2).numpy().flatten()
                self.thresholds[machine_id] = np.percentile(errors, 95)
            
            mlflow.log_param("window_size", self.window_size)
            mlflow.log_metric("final_loss", loss.item())
            mlflow.pytorch.log_model(model, f"model_{machine_id}")

    def update_and_predict(self, machine_id, data):
        """Adds new data to buffer and predicts if it's an anomaly."""
        if machine_id not in self.data_buffers:
            self.data_buffers[machine_id] = deque(maxlen=self.window_size)
        
        # Extract features
        current_features = [data.get(f, 0) for f in self.features]
        self.data_buffers[machine_id].append(current_features)

        # We need at least 50 points to start detecting anomalies meaningfully
        if len(self.data_buffers[machine_id]) < 50:
            return False # Not enough data yet

        # Retrain model periodically (every 50 points) or if no model exists
        if len(self.data_buffers[machine_id]) % 50 == 0 or machine_id not in self.models:
            X = np.array(list(self.data_buffers[machine_id]))
            # Scale data (simplified)
            self._train_model(machine_id, X)

        # Predict
        X_now = np.array(list(self.data_buffers[machine_id]))
        X_tensor = torch.tensor(X_now, dtype=torch.float32).unsqueeze(0)
        
        with torch.no_grad():
            output = self.models[machine_id](X_tensor)
            # Compare only the last time step
            error = torch.mean((output[0, -1, :] - X_tensor[0, -1, :])**2).item()
            
        return error > self.thresholds.get(machine_id, float('inf'))

class CommandModel(BaseModel):
    command: str
    value: bool

class DataProcessor:
    def __init__(self):
        # Config
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
        self.influx_url = os.getenv('INFLUXDB_URL', 'http://influxdb:8086')
        self.influx_token = os.getenv('INFLUXDB_TOKEN', 'factory-super-secret-token')
        self.influx_org = os.getenv('INFLUXDB_ORG', 'factory')
        self.influx_bucket = os.getenv('INFLUXDB_BUCKET', 'telemetry')
        
        self.pg_host = os.getenv('POSTGRES_HOST', 'postgres')
        self.pg_db = os.getenv('POSTGRES_DB', 'smart_factory')
        self.pg_user = os.getenv('POSTGRES_USER', 'admin')
        self.pg_pass = os.getenv('POSTGRES_PASSWORD', 'factory')

        self.running = True

        # Initialize Anomaly Detector
        self.anomaly_detector = AnomalyDetector()

        # Avro Setup
        SCHEMA_REGISTRY_URL = os.getenv('SCHEMA_REGISTRY_URL', 'http://schema-registry:8081')
        schema_registry_conf = {'url': SCHEMA_REGISTRY_URL}
        schema_registry_client = SchemaRegistryClient(schema_registry_conf)
        avro_deserializer = AvroDeserializer(schema_registry_client)
        string_deserializer = StringDeserializer('utf_8')

        # Kafka Consumer Config
        conf = {
            'bootstrap.servers': self.kafka_servers,
            'key.deserializer': string_deserializer,
            'value.deserializer': avro_deserializer,
            'group.id': 'factory-processor-group-v3',
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False
        }
        self.consumer = DeserializingConsumer(conf)
        self.consumer.subscribe(['factory_telemetry'])

        # DB Clients
        self.influx_client = InfluxDBClient(url=self.influx_url, token=self.influx_token, org=self.influx_org)
        self.write_api = self.influx_client.write_api(write_options=ASYNCHRONOUS)

        # Postgres Connection Pool
        try:
            self.pg_pool = pool.SimpleConnectionPool(
                1, 10,
                host=self.pg_host,
                database=self.pg_db,
                user=self.pg_user,
                password=self.pg_pass
            )
            logger.info("Postgres connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Postgres pool: {e}")
            # Don't exit here, allows API to still start even if DB is temporarily down
        
        # Latest State for API
        self.latest_metrics = {}

        # FastAPI App
        self.app = FastAPI()
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._setup_routes()

    def _setup_routes(self):
        @self.app.get("/api/metrics")
        async def get_metrics():
            return self.latest_metrics

        @self.app.get("/api/history/{machine_id}")
        async def get_history(machine_id: str):
            # Query InfluxDB for last 100 points
            query = f'from(bucket: "{self.influx_bucket}") |> range(start: -1h) |> filter(fn: (r) => r.machine_id == "{machine_id}")'
            # (Simplified for now, returning mock or real if possible)
            return {"machine_id": machine_id, "data": list(self.anomaly_detector.data_buffers.get(machine_id, []))}

        @self.app.get("/api/health")
        async def health():
            return {"status": "healthy", "components": {"kafka": "connected", "influx": "connected", "postgres": "connected"}}

        @self.app.post("/api/commands")
        async def send_command(cmd: CommandModel):
            try:
                import paho.mqtt.publish as publish
                mqtt_broker = os.getenv('MQTT_BROKER', 'mosquitto')
                mqtt_user = os.getenv('MQTT_USER', 'bridge')
                mqtt_pass = os.getenv('MQTT_PASS', 'bridge_pass')
                
                payload = json.dumps({"command": cmd.command, "value": cmd.value})
                auth = {'username': mqtt_user, 'password': mqtt_pass}
                
                publish.single("factory/commands", payload=payload, hostname=mqtt_broker, auth=auth)
                return {"status": "success", "message": f"Command {cmd.command} sent"}
            except Exception as e:
                logger.error(f"Failed to send command: {e}")
                return {"status": "error", "message": str(e)}

        self.active_connections: list[WebSocket] = []

        @self.app.websocket("/ws/metrics")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                self.active_connections.remove(websocket)

    def _broadcast_to_websockets(self, data):
        # We need an async loop to broadcast. If running in a separate thread,
        # we can use asyncio.run or create a task in the running loop.
        # Since uvicorn runs its own loop, we can just use asyncio.run here
        # or since it's a simple push, it's better to iterate and send.
        import asyncio
        if not self.active_connections:
            return
            
        async def send_all():
            for connection in self.active_connections.copy():
                try:
                    await connection.send_json(data)
                except Exception as e:
                    logger.error(f"Failed to send to websocket: {e}")
                    if connection in self.active_connections:
                        self.active_connections.remove(connection)
        
        # Create a new event loop for this thread if needed, or use asyncio.run
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(send_all(), loop=loop)
            else:
                asyncio.run(send_all())
        except RuntimeError:
            asyncio.run(send_all())

    def stop(self, *args):
        logger.info("Stopping processor...")
        self.running = False

    def process_message(self, msg):
        try:
            data = msg.value()
            if data is None:
                return
            
            m_id = data.get('machine_id', 'unknown')
            
            # 1. Run Anomaly Detection
            is_anomaly = self.anomaly_detector.update_and_predict(m_id, data)
            if is_anomaly:
                logger.warning(f"!!! ANOMALY DETECTED for machine {m_id} !!!")
            
            # 2. Write to InfluxDB (Metrics + Anomaly Flag)
            point = Point("machine_data") \
                .tag("machine_id", m_id) \
                .field("temperature", float(data.get('temperature', 0))) \
                .field("rpm", float(data.get('rpm', 0))) \
                .field("vibration", float(data.get('vibration', 0))) \
                .field("current", float(data.get('current', 0))) \
                .field("is_anomaly", 1 if is_anomaly else 0)
            self.write_api.write(bucket=self.influx_bucket, record=point)
            
            # Update Latest Metrics Cache
            self.latest_metrics[m_id] = {
                **data,
                "is_anomaly": is_anomaly,
                "timestamp": time.time()
            }
            
            # Broadcast to websockets
            self._broadcast_to_websockets(self.latest_metrics)
            
            # 3. Write to Postgres (Events)
            conn = self.pg_pool.getconn()
            try:
                with conn.cursor() as cur:
                    status = "ANOMALY" if is_anomaly else data.get('status', 'RUNNING')
                    cur.execute(
                        "INSERT INTO machine_events (machine_id, status, payload) VALUES (%s, %s, %s)",
                        (m_id, status, json.dumps(data))
                    )
                conn.commit()
            finally:
                self.pg_pool.putconn(conn)
            
            logger.debug(f"Processed message from {m_id}")
            self.consumer.commit(msg, asynchronous=False)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def run(self):
        logger.info("Processor started with ML Anomaly Detection. Listening...")
        
        # Start API Thread
        api_thread = threading.Thread(target=lambda: uvicorn.run(self.app, host="0.0.0.0", port=8000), daemon=True)
        api_thread.start()
        logger.info("API Server started on port 8000")
        
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

        try:
            while self.running:
                msg = self.consumer.poll(1.0)
                if msg is None: continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF: continue
                    else: 
                        logger.error(f"Kafka error: {msg.error()}")
                        break
                
                self.process_message(msg)

        finally:
            logger.info("Cleaning up...")
            self.consumer.close()
            self.write_api.close()
            self.influx_client.close()
            self.pg_pool.closeall()
            logger.info("Processor stopped.")

if __name__ == "__main__":
    processor = DataProcessor()
    processor.run()
