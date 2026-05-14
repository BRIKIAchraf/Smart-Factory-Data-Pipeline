import time
import json
import os
import logging
import signal
import sys
import sqlite3
import threading
from pymodbus.client import ModbusTcpClient
import paho.mqtt.client as mqtt

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("EdgeGateway")

class EdgeGateway:
    def __init__(self):
        # Config from ENV
        self.plc_host = os.getenv('PLC_HOST', 'localhost')
        self.plc_port = int(os.getenv('PLC_PORT', 502))
        self.mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
        self.mqtt_port = int(os.getenv('MQTT_PORT', 1883))
        self.mqtt_user = os.getenv('MQTT_USER', 'gateway')
        self.mqtt_pass = os.getenv('MQTT_PASS', 'gateway_pass')
        self.machine_id = os.getenv('MACHINE_ID', 'motor_01')
        self.base_topic = f"factory/line_A/{self.machine_id}"
        self.db_path = os.getenv('GATEWAY_DB', 'gateway_buffer.db')
        
        self.running = True
        self.mqtt_connected = False
        
        # Edge Pre-processing Buffer
        self.preprocessing_window = 5 # Calculate average over 5 samples
        self.reading_buffer = []
        
        # Initialize SQLite Buffer
        self._init_db()
        
        # Initialize MQTT Client
        self.mqtt_client = mqtt.Client(client_id=f"gateway_{self.machine_id}")
        self.mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_pass)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.command_topic = "factory/commands"
        
        # Industrial Req: Last Will and Testament
        lwt_payload = json.dumps({"machine_id": self.machine_id, "status": "OFFLINE", "reason": "unexpected_disconnect"})
        self.mqtt_client.will_set(f"{self.base_topic}/status", lwt_payload, qos=1, retain=True)

        # Initialize Modbus Client
        self.plc_client = ModbusTcpClient(self.plc_host, port=self.plc_port)

    def _init_db(self):
        """Initializes the local SQLite database for store-and-forward buffering."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS telemetry_buffer (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        topic TEXT,
                        payload TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            logger.info(f"Local buffer initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize local buffer: {e}")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT Broker")
            self.mqtt_connected = True
            # Publish Online Status
            self.mqtt_client.publish(f"{self.base_topic}/status", 
                                     json.dumps({"machine_id": self.machine_id, "status": "ONLINE"}), 
                                     qos=1, retain=True)
            self.mqtt_client.subscribe(self.command_topic, qos=1)
            # Start draining buffer in a separate thread
            threading.Thread(target=self.drain_buffer, daemon=True).start()
        else:
            logger.error(f"Failed to connect to MQTT, return code {rc}")

    def on_mqtt_disconnect(self, client, userdata, rc):
        logger.warning(f"Disconnected from MQTT Broker (rc: {rc})")
        self.mqtt_connected = False

    def on_mqtt_message(self, client, userdata, message):
        if message.topic == self.command_topic:
            try:
                data = json.loads(message.payload.decode())
                if data.get("command") == "E_STOP":
                    is_active = data.get("value", True)
                    logger.warning(f"Received E_STOP command: {is_active}")
                    if self.plc_client.connected:
                        # Write to Coil 2 (%QX0.2)
                        res = self.plc_client.write_coil(2, is_active)
                        if res.isError():
                            logger.error(f"Failed to write E_STOP to PLC: {res}")
                        else:
                            logger.info("E_STOP successfully written to PLC")
                    else:
                        logger.error("Cannot write E_STOP: PLC not connected")
            except Exception as e:
                logger.error(f"Error processing command message: {e}")

    def buffer_data(self, topic, payload):
        """Stores data in local SQLite when MQTT is down."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("INSERT INTO telemetry_buffer (topic, payload) VALUES (?, ?)", 
                             (topic, json.dumps(payload)))
            logger.debug("Telemetry buffered locally.")
        except Exception as e:
            logger.error(f"Error buffering data: {e}")

    def drain_buffer(self):
        """Sends buffered data to MQTT once connection is restored."""
        if not self.mqtt_connected:
            return

        logger.info("Draining local buffer...")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT id, topic, payload FROM telemetry_buffer ORDER BY id ASC LIMIT 100")
                rows = cursor.fetchall()
                
                while rows and self.mqtt_connected:
                    for row_id, topic, payload in rows:
                        # Add a flag to indicate this is historical data
                        data = json.loads(payload)
                        data["buffered"] = True
                        
                        res = self.mqtt_client.publish(topic, json.dumps(data), qos=1)
                        res.wait_for_publish()
                        
                        if res.rc == mqtt.MQTT_ERR_SUCCESS:
                            conn.execute("DELETE FROM telemetry_buffer WHERE id = ?", (row_id,))
                        else:
                            break
                    
                    conn.commit()
                    cursor = conn.execute("SELECT id, topic, payload FROM telemetry_buffer ORDER BY id ASC LIMIT 100")
                    rows = cursor.fetchall()
            
            logger.info("Buffer drained successfully.")
        except Exception as e:
            logger.error(f"Error draining buffer: {e}")

    def stop(self, *args):
        logger.info("Stopping gateway...")
        self.running = False
        self.mqtt_client.publish(f"{self.base_topic}/status", 
                                 json.dumps({"machine_id": self.machine_id, "status": "OFFLINE", "reason": "graceful_shutdown"}), 
                                 qos=1, retain=True)
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.plc_client.close()
        logger.info("Gateway stopped.")
        sys.exit(0)

    def run(self):
        logger.info(f"Starting Edge Gateway for {self.machine_id}...")
        
        # Connect to MQTT
        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            logger.error(f"Initial MQTT connection failed: {e}")

        # Register signals
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

        while self.running:
            try:
                # Ensure PLC Connection
                if not self.plc_client.connected:
                    if not self.plc_client.connect():
                        logger.warning(f"Failed to connect to PLC at {self.plc_host}:{self.plc_port}. Retrying...")
                        time.sleep(5)
                        continue
                
                # Read Holding Registers (0-3: Temp, RPM, Vib, Current)
                result = self.plc_client.read_holding_registers(0, 4)
                
                if not result.isError():
                    raw_payload = {
                        "temperature": result.registers[0],
                        "rpm": result.registers[1],
                        "vibration": result.registers[2],
                        "current": result.registers[3] / 10.0
                    }
                    self.reading_buffer.append(raw_payload)
                    
                    if len(self.reading_buffer) >= self.preprocessing_window:
                        # Edge Pre-processing: Calculate Moving Average
                        avg_temp = sum(p['temperature'] for p in self.reading_buffer) / self.preprocessing_window
                        avg_rpm = sum(p['rpm'] for p in self.reading_buffer) / self.preprocessing_window
                        avg_vib = sum(p['vibration'] for p in self.reading_buffer) / self.preprocessing_window
                        avg_curr = sum(p['current'] for p in self.reading_buffer) / self.preprocessing_window
                        
                        payload = {
                            "machine_id": self.machine_id,
                            "timestamp": time.time(),
                            "temperature": avg_temp,
                            "rpm": avg_rpm,
                            "vibration": avg_vib,
                            "current": avg_curr,
                            "status": "RUNNING" if avg_rpm > 0 else "STOPPED"
                        }
                        self.reading_buffer.clear() # Reset buffer
                        
                        topic = f"{self.base_topic}/telemetry"
                        if self.mqtt_connected:
                            self.mqtt_client.publish(topic, json.dumps(payload), qos=1)
                        else:
                            logger.warning("MQTT offline, buffering data...")
                            self.buffer_data(topic, payload)
                else:
                    logger.error(f"Modbus Read Error: {result}")
                
                time.sleep(0.5)

            except Exception as e:
                logger.exception(f"Unexpected error in main loop: {e}")
                time.sleep(5)

if __name__ == "__main__":
    gateway = EdgeGateway()
    gateway.run()
