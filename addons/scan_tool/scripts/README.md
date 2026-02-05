# ELM327 Simulator Service Scripts

Control scripts for starting/stopping the ELM327 OBD-II simulator.

## Linux

### Quick Start
```bash
# Start simulator
./elm327_simulator.sh start

# Check status
./elm327_simulator.sh status

# Stop simulator
./elm327_simulator.sh stop

# View logs
./elm327_simulator.sh logs
```

### Environment Variables
- `ELM327_SIM_PORT` - Port to listen on (default: 35000)
- `ELM327_SIM_HOST` - Host to bind to (default: 0.0.0.0)
- `ELM327_SIM_STATE` - Vehicle state to simulate (default: lean_both_banks)

Example:
```bash
ELM327_SIM_STATE=overheating ./elm327_simulator.sh start
```

### Systemd Service (Optional)

To install as a systemd service:

```bash
# Copy service file
sudo cp elm327-simulator.service /etc/systemd/system/

# Edit if needed (adjust paths, user)
sudo nano /etc/systemd/system/elm327-simulator.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable elm327-simulator
sudo systemctl start elm327-simulator

# Check status
sudo systemctl status elm327-simulator
```

## Windows

### Batch Script
```cmd
REM Start simulator
elm327_simulator.bat start

REM Start with specific state
elm327_simulator.bat start overheating

REM Check status
elm327_simulator.bat status

REM Stop simulator
elm327_simulator.bat stop
```

### PowerShell Script
```powershell
# Start simulator
.\elm327_simulator.ps1 Start

# Start with specific state
.\elm327_simulator.ps1 Start -State overheating -Port 35000

# Check status
.\elm327_simulator.ps1 Status

# Stop simulator
.\elm327_simulator.ps1 Stop

# View logs
.\elm327_simulator.ps1 Logs
```

## Vehicle States

Available simulated vehicle conditions:

| State | Description | DTCs |
|-------|-------------|------|
| `normal` | Healthy vehicle | None |
| `overheating` | Stuck thermostat | P0217 (Overheat) |
| `running_cold` | Thermostat stuck open | P0128 (Coolant temp below threshold) |
| `lean_both_banks` | Vacuum leak | P0171, P0174 (System lean) |
| `lean_bank1` | Bank 1 specific lean | P0171 |
| `rich_both_banks` | Over-fueling | P0172, P0175 (System rich) |
| `misfire_cyl3` | Cylinder 3 misfire | P0303 |
| `random_misfire` | Multiple cylinders | P0300 |
| `cat_degraded` | Catalytic converter | P0420 |
| `o2_sensor_lazy` | Slow O2 response | P0133 |
| `maf_dirty` | Contaminated MAF sensor | P0101 |

## Testing the Simulator

Once running, you can connect with:

```bash
# Linux/Mac
nc localhost 35000

# Windows
telnet localhost 35000
```

Send ELM327 commands:
```
ATZ          # Reset
ATE0         # Echo off
03           # Read DTCs
010C         # Read RPM
```

## Gateway Integration

The simulator works with the ELM327 Gateway:

```bash
# Start simulator
./elm327_simulator.sh start

# Start gateway (connects to simulator)
python -m addons.scan_tool.gateway.server --port 8327

# Now Open WebUI tools can use the simulator via the gateway
```
