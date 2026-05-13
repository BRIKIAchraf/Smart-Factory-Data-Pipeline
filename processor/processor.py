import json
import os
import logging
import signal
import sys
import time
from confluent_kafka import Consumer, KafkaError
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS, ASYNCHRONOUS
from psycopg2 import pool

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("Processor")

class DataProcessor:
    def __init__(self):
        # Config
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
        self.influx_url = os.getenv('INFLUXDB_URL', 'http://influxdb:8086')
        self.influx_token = os.getenv('INFLUXDB_TOKEN', 'factory-super-secret-token')
        self.influx_org = os.getenv('INFLUX_ORG', 'factory')
        self.influx_bucket = os.getenv('INFLUX_BUCKET', 'telemetry')
        
        self.pg_host = os.getenv('POSTGRES_HOST', 'postgres')
        self.pg_db = os.getenv('POSTGRES_DB', 'factory_db')
        self.pg_user = os.getenv('POSTGRES_USER', 'admin')
        self.pg_pass = os.getenv('POSTGRES_PASSWORD', 'factory123')

        self.running = True

        # Kafka Consumer Config
        conf = {
            'bootstrap.servers': self.kafka_servers,
            'group.id': 'factory-processor-group-v2',
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False
        }
        self.consumer = Consumer(conf)
        self.consumer.subscribe(['factory_telemetry'])

        # DB Clients
        self.influx_client = InfluxDBClient(url=self.influx_url, token=self.influx_token, org=self.influx_org)
        # Using ASYNCHRONOUS for better performance (batching)
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
            sys.exit(1)

    def stop(self, *args):
        logger.info("Stopping processor...")
        self.running = False

    def process_message(self, msg):
        try:
            data = json.loads(msg.value().decode('utf-8'))
            m_id = data.get('machine_id', 'unknown')
            
            # 1. Write to InfluxDB (Metrics)
            point = Point("machine_data") \
                .tag("machine_id", m_id) \
                .field("temperature", float(data.get('temperature', 0))) \
                .field("rpm", float(data.get('rpm', 0))) \
                .field("vibration", float(data.get('vibration', 0))) \
                .field("current", float(data.get('current', 0)))
            self.write_api.write(bucket=self.influx_bucket, record=point)
            
            # 2. Write to Postgres (Events)
            conn = self.pg_pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO machine_events (machine_id, status, payload) VALUES (%s, %s, %s)",
                        (m_id, data.get('status', 'UNKNOWN'), json.dumps(data))
                    )
                conn.commit()
            finally:
                self.pg_pool.putconn(conn)
            
            logger.debug(f"Processed message from {m_id}")
            
            # Commit offset
            self.consumer.commit(msg, asynchronous=False)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def run(self):
        logger.info("Processor started. Listening for Kafka messages...")
        
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
