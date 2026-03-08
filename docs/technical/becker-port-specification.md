# DriveWire Becker Port Technical Specification

## 1. Introduction

The Becker Port is a high-speed I/O interface designed for CoCo emulators and integration with Gary Becker’s CoCo3FPGA project. It facilitates rapid data transfer between a CoCo system and a DriveWire server by assuming external hardware manages the physical I/O connections and provides buffering.

This specification outlines the register map and operational principles of the Becker Port.

## 2. Register Map

The Becker Port utilizes two memory-mapped addresses for communication: a status register and a data register.

| Register Name   | Address (Hex) | Description                                  |
|-----------------|----------------|----------------------------------------------|
| Status Register | &HFF41         | Indicates data availability for reading.     |
| Data Register   | &HFF42         | Used for both reading and writing data.      |

### 2.1 Status Register (&HFF41)

The Status Register indicates whether data is available to be read from the Data Register. 

| Bit | Name      | Description                             | Value when set (Data Available) |
|-----|-----------|-----------------------------------------|---------------------------------|
| 1   | DataReady | Indicates data is available to be read. | 1                               |

> [!NOTE]
> The DataReady bit must be polled by the CoCo before attempting to read data from the Data Register.

## 3. Operational Theory

### 3.1 Data Reading

1. **Status Check**: The CoCo reads the Status Register (&HFF41).
2. **Data Ready**: If bit #1 (DataReady) is '1', data is available.
3. **Data Read**: The CoCo reads a byte from the Data Register (&HFF42).
4. **Auto-Clear**: The external hardware clears the DataReady bit after the read is completed.

### 3.2 Data Writing

1. **Data Write**: The CoCo writes a byte of data to the Data Register (&HFF42).
2. **Data Transfer**: The external hardware receives the data and transmits it to the DriveWire server.

---
[Return to Documentation Index](../index.md)
