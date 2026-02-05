# Autotech AI Predictive Diagnostics

## Product Overview

Autotech AI Predictive Diagnostics is an AI-powered diagnostic engine that transforms automotive troubleshooting from a 1-2 hour manual process into a 5-minute guided diagnosis.

**Core Value Proposition:** From "car runs rough" to "here are the 3 most likely root causes with confidence scores" — in seconds, not hours.

---

## How It Works

### The Diagnostic Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI Diagnostic Assistant                      │
│              (Automotive reasoning + ML predictions)             │
│                                                                  │
│   Combines pattern-matching results with deep automotive         │
│   knowledge to guide technicians through diagnosis               │
└─────────────────────────────────────────────────────────────────┘
          ▲                                        │
          │ ML predictions                         │ Guided diagnosis
          │ + confidence scores                    │ + next steps
          │                                        ▼
┌─────────────────────┐                  ┌─────────────────────┐
│  ML Pattern Engine  │                  │  Optional: TSB/Spec │
│  (Proprietary)      │                  │  Lookup Integration │
└─────────────────────┘                  └─────────────────────┘
          ▲                                        
          │ Live OBD-II data                       
┌─────────────────────┐                  
│   Vehicle Scanner   │                  
│   (ELM327/J2534)    │                  
└─────────────────────┘                  
```

---

## Core Features (Included)

### 1. ML-Powered Pattern Recognition Engine

**What it does:**
- Analyzes real-time OBD-II sensor data (20+ parameters)
- Compares patterns against thousands of simulated failure scenarios
- Returns ranked list of probable root causes with confidence scores

**How it works:**
- Trained on physics-simulated vehicle failures (PyChrono engine)
- 45+ failure modes across 10 vehicle systems
- Learns subtle multi-sensor correlations humans miss

**Example output:**
```
System: Cooling
Predictions:
  1. Fan relay failure (87% confidence)
  2. Thermostat stuck closed (9%)
  3. Radiator blockage (3%)
```

**Why it's valuable:**
- Catches patterns across multiple sensors simultaneously
- No confirmation bias ("it's always the thermostat")
- Milliseconds vs. 30 minutes of manual diagnosis
- Works even without DTCs present

### 2. AI Diagnostic Assistant

**What it does:**
- Interprets ML predictions in context
- Provides vehicle-specific guidance based on year/make/model
- Suggests targeted tests to confirm diagnosis
- Explains the "why" behind each prediction

**Example interaction:**
```
Tech: "2018 Honda Accord runs hot at idle"

AI: "Based on the sensor pattern (coolant rising 0.3°C/sec, 
     fan not activating, stable RPM), the ML engine predicts 
     fan relay failure with 87% confidence.
     
     Suggested verification:
     1. Check for 12V at fan relay coil (pin 85)
     2. Jump relay - if fan runs, relay is faulty
     3. Known issue on 2017-2019 Accords - check connector C101 
        for corrosion
     
     If relay tests good, next check thermostat operation..."
```

### 3. Real-Time OBD-II Data Capture

**What it does:**
- Connects to vehicle via ELM327 or J2534 interface
- Captures live sensor streams during test drive or idle
- Monitors: RPM, temps, fuel trims, pressures, and more

**Features:**
- Automatic PID detection for vehicle compatibility
- 30-second capture window for pattern analysis
- Works with standard OBD-II port (1996+ vehicles)
- Simulator mode for training and demos

### 4. Hierarchical System Analysis

**Vehicle systems covered:**
| System | Failure Modes | Description |
|--------|---------------|-------------|
| Cooling | 10+ | Thermostat, water pump, radiator, fan, sensors |
| Fuel | 11+ | Pump, filter, injectors, pressure regulator, MAF |
| Ignition | 3+ | Spark, coils, knock sensor |
| Charging | 2+ | Alternator, battery |
| Transmission | 3+ | Fluid, slipping, torque converter |
| Brakes | 1+ | Brake fade, pad wear |
| Tires | 2+ | Pressure, wear |
| Starting | 1+ | Starter motor |
| Engine | 1+ | Oil pump |
| EV Systems | 1+ | HV isolation (Tesla/EV) |

---

## Optional Integrations (Customer-Provided Credentials)

### Mitchell/ShopKeyPro Integration

**Requires:** Customer's own Mitchell/ShopKeyPro subscription

**What it adds:**
- TSB (Technical Service Bulletin) lookup
- OEM repair procedures
- Wiring diagrams
- Fluid capacities and torque specs

**How it works:**
- Customer provides their Mitchell credentials
- System accesses their subscription on their behalf
- AI incorporates TSB info into diagnosis guidance

**Important:** We do not store, redistribute, or resell Mitchell data. Each shop accesses their own subscription.

### AllData Integration (Planned)

- Similar to Mitchell integration
- Customer provides their own AllData credentials

---

## What's NOT Included

| Feature | Status | Notes |
|---------|--------|-------|
| TSB database | ❌ | Requires customer's Mitchell/AllData subscription |
| Wiring diagrams | ❌ | Requires customer's Mitchell/AllData subscription |
| OEM repair procedures | ❌ | Requires customer's Mitchell/AllData subscription |
| Parts pricing | ❌ | Future integration planned |
| Labor time estimates | ❌ | Future integration planned |

---

## Technical Architecture

### Proprietary Components (Our IP)

1. **PyChrono Training Pipeline**
   - Physics-based vehicle simulation
   - Fault injection framework
   - Synthetic training data generation

2. **Hierarchical ML Models**
   - Per-system neural network classifiers
   - 11-feature extraction per sensor
   - Trained on 20,000+ simulated scenarios

3. **Inference Engine**
   - Real-time pattern matching
   - Confidence scoring
   - Ambiguity detection

4. **AI Integration Layer**
   - Prompt engineering for automotive context
   - Tool orchestration (scan tool + TSB lookup)
   - Conversational diagnosis flow

### Data Sources

| Data | Source | Ownership |
|------|--------|-----------|
| ML training data | PyChrono simulation | Ours (proprietary) |
| OBD-II sensor data | Customer's vehicles | Customer's |
| TSBs/procedures | Mitchell/AllData | Customer's subscription |
| AI automotive knowledge | LLM training | LLM provider |

---

## Deployment Options

### Cloud (SaaS)
- Hosted on Autotech AI servers
- Web interface via Open WebUI
- API access for integration

### On-Premise (Enterprise)
- Docker deployment
- Runs on shop's local hardware
- Data stays on-site

### Hybrid
- ML inference in cloud
- Scan tool connection local
- Mitchell access via customer's network

---

## Competitive Advantages

### vs. Traditional Scan Tools
| Feature | Traditional | Autotech AI |
|---------|-------------|-------------|
| DTC lookup | ✓ | ✓ |
| Root cause from DTCs | ❌ | ✓ |
| Pattern detection (no DTC) | ❌ | ✓ |
| AI-guided next steps | ❌ | ✓ |
| Multi-sensor correlation | ❌ | ✓ |

### vs. Human Expert
| Feature | Human Expert | Autotech AI |
|---------|--------------|-------------|
| Speed | 30-60 min | < 1 min |
| Consistency | Varies | Consistent |
| Subtle patterns | Sometimes | Always |
| Available 24/7 | ❌ | ✓ |
| Scales to 100 bays | ❌ | ✓ |

### vs. Generic AI Chatbots
| Feature | Generic AI | Autotech AI |
|---------|------------|-------------|
| Real OBD-II data | ❌ | ✓ |
| ML pattern matching | ❌ | ✓ |
| Vehicle-specific | Limited | Deep |
| Trained on failures | ❌ | ✓ |

---

## Pricing Model (Draft)

| Tier | Features | Price |
|------|----------|-------|
| **Starter** | ML diagnosis, AI assistant, 1 bay | $X/mo |
| **Professional** | + Mitchell integration, 5 bays | $Y/mo |
| **Enterprise** | + On-premise, unlimited bays, API | Custom |

*Mitchell/AllData subscriptions sold separately by those vendors.*

---

## Roadmap

### Now (Q1 2026)
- ✅ ML pattern recognition engine
- ✅ ELM327 scan tool integration
- ✅ AI diagnostic assistant
- ✅ Mitchell integration (BYOC - Bring Your Own Credentials)

### Next (Q2 2026)
- [ ] AllData integration
- [ ] NHTSA recall/TSB lookup (free, no subscription needed)
- [ ] Mobile app for technicians
- [ ] Expanded failure mode library (100+)

### Future
- [ ] Parts ordering integration
- [ ] Labor time estimates
- [ ] Shop management system integrations
- [ ] Predictive maintenance (before failure occurs)

---

## Contact

**Autotech AI**  
Website: automotive.aurora-sentient.net  
Email: [contact info]

---

*Document Version: 1.0*  
*Last Updated: January 2026*
