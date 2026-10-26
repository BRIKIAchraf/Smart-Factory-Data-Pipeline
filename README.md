

## About

Event-driven industrial data pipeline that transports machine telemetry from PLC/Modbus and MQTT into Kafka, InfluxDB, PostgreSQL and operational dashboards.
# Smart Factory Data Pipeline

Event-driven industrial IoT pipeline for collecting, processing and visualising machine telemetry.

## Objective

Bridge operational technology and data-platform components so that machine signals can be monitored in near real time while remaining recoverable during connectivity failures.

## Architecture

~~~text
OpenPLC / Modbus simulator → Edge Gateway
                                  ↓ MQTT
                              Mosquitto
                                  ↓ bridge
                                Kafka
                                  ↓
                            Data processor
                         ↙                   ↘
                  InfluxDB telemetry     PostgreSQL events
                         ↓                   ↓
                         Grafana / React control centre
~~~

## Core capabilities

- Modbus/TCP polling at the configured edge interval;
- MQTT QoS 1 transport and Kafka event backbone;
- local SQLite store-and-forward buffer;
- explicit Kafka offset handling and reconnect/watchdog logic;
- high-resolution telemetry in InfluxDB;
- structured events and configuration data in PostgreSQL;
- Grafana dashboards and a React operations interface;
- anomaly signals based on configurable or unsupervised processing.

## Technology stack

Python · PyModbus · Paho-MQTT · Mosquitto · Apache Kafka · InfluxDB · PostgreSQL · Grafana · React · Vite · Docker Compose

## Quick start

Prerequisites: Docker, Docker Compose and Node.js for the dashboard.

~~~bash
docker compose up -d
~~~

Start the dashboard with the project-specific frontend command. Verify the local ports and credentials in the environment configuration before sharing the system.

## Reliability model

The pipeline is designed around store-and-forward and explicit recovery. It is not a guarantee of zero data loss until the full failure matrix, duplicate handling, retention and recovery time objectives have been tested.

## Status

Portfolio implementation and industrial simulation. Hardware, network security, high-volume throughput and failover require additional validation.

## Author

**Achraf BRIKI** · [LinkedIn](https://www.linkedin.com/in/achrafbriki/) · [Portfolio](https://achrafbriki.com)

## Delivery profile

**Status:** MVP  
**Demo:** Local Docker deployment with simulated PLC telemetry, MQTT/Kafka, InfluxDB, PostgreSQL and dashboards.  
**Prerequisites:** Docker Compose and Node.js for the dashboard.  
**Validation:** Store-and-forward, reconnects, duplicates, offsets, watchdog recovery and dashboard freshness.  
**Performance plan:** Measure telemetry rate, buffer growth, latency, consumer lag and recovery time.  
**Roadmap:** Integration/resilience tests, telemetry contracts, CI, retention policies and load testing.
