import time
import json
import os
import logging
import signal
import sys
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
        self.machine_id = os.getenv('MACHINE_ID', 'motor_01')
        self.base_topic = f"factory/line_A/{self.machine_id}"
        
        self.running = True
        self.mqtt_connected = False
        
        # Initialize MQTT Client
        self.mqtt_client = mqtt.Client(client_id=f"gateway_{self.machine_id}")
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        
        # Industrial Req: Last Will and Testament
        lwt_payload = json.dumps({"machine_id": self.machine_id, "status": "OFFLINE", "reason": "unexpected_disconnect"})
        self.mqtt_client.will_set(f"{self.base_topic}/status", lwt_payload, qos=1, retain=True)

        # Initialize Modbus Client
        self.plc_client = ModbusTcpClient(self.plc_host, port=self.plc_port)

    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT Broker")
            self.mqtt_connected = True
            # Publish Online Status
            self.mqtt_client.publish(f"{self.base_topic}/status", 
                                     json.dumps({"machine_id": self.machine_id, "status": "ONLINE"}), 
                                     qos=1, retain=True)
        else:
            logger.error(f"Failed to connect to MQTT, return code {rc}")

    def on_mqtt_disconnect(self, client, userdata, rc):
        logger.warning(f"Disconnected from MQTT Broker (rc: {rc})")
        self.mqtt_connected = False

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
                    payload = {
                        "machine_id": self.machine_id,
                        "timestamp": time.time(),
                        "temperature": result.registers[0],
                        "rpm": result.registers[1],
                        "vibration": result.registers[2],
                        "current": result.registers[3] / 10.0, # Scaled value
                        "status": "RUNNING" if result.registers[1] > 0 else "STOPPED"
                    }
                    
                    if self.mqtt_connected:
                        self.mqtt_client.publish(f"{self.base_topic}/telemetry", json.dumps(payload), qos=1)
                        logger.debug(f"Published telemetry: {payload}")
                    else:
                        logger.warning("MQTT not connected, skipping publish")
                else:
                    logger.error(f"Modbus Read Error: {result}")
                
                time.sleep(0.5)

            except Exception as e:
                logger.exception(f"Unexpected error in main loop: {e}")
                time.sleep(5)

if __name__ == "__main__":
    gateway = EdgeGateway()
    gateway.run()
