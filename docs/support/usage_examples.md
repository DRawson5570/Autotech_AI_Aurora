# Autotech AI Usage Examples

Real-world examples showing how Autotech AI's diagnostic reasoning and automotive systems knowledge can help you work smarter.

---

## Choosing the Right Model

Different models are optimized for different tasks. Here's when to use each:

### Autotech AI Expert
**Best for:** Diagnostic reasoning, system knowledge, troubleshooting strategy

Use when you need:
- Differential diagnosis from symptoms
- Understanding how systems interact
- "Why did this fail?" analysis
- Diagnostic test sequences
- Pattern recognition across vehicles
- Customer explanations

**Example questions:**
- "Customer has intermittent no-start on cold mornings. What should I check?"
- "Why would a P0420 keep coming back after replacing the cat?"
- "What could cause repeat alternator failures?"

### AutoDB
**Best for:** Specific specifications and owner's manual data

Use when you need:
- Fluid capacities (oil, coolant, transmission)
- Torque specifications
- Tire pressures
- Maintenance intervals
- Owner's manual procedures
- Reset procedures

**Example questions:**
- "Oil capacity for 2019 Toyota Camry 2.5L"
- "Lug nut torque for 2020 Honda CR-V"
- "Coolant type for 2018 Ford F-150 3.5 EcoBoost"

### Autotech AI Support
**Best for:** Learning how to use this platform

Use when you need:
- Help with features
- "How do I..." questions about the app
- Troubleshooting platform issues

---

## Diagnostic Reasoning from Symptoms

**Describe symptoms in plain English and get a differential diagnosis with reasoning.**

### Example: Intermittent No-Start

**Your question:**
> 2018 Ford F-150 3.5 EcoBoost. Customer says truck won't start sometimes, especially in the morning. Cranks fine but won't fire. After a few tries it starts and runs fine all day. No check engine light.

**AI provides:**
- Likely causes ranked by probability (fuel pressure bleed-down, EVAP purge valve stuck open, weak fuel pump check valve)
- Specific tests to isolate the cause (residual fuel pressure test after sitting overnight)
- Why morning vs. afternoon matters (thermal cycling, pressure decay time)
- Which components share the symptom pattern

**Why this is powerful:** Instead of throwing parts at it, you get a diagnostic strategy that pinpoints the root cause.

---

## Understanding What DTCs Really Mean

**Go beyond "what the code says" to understand what's actually happening in the system.**

### Example: P0420 Catalyst Efficiency

**Your question:**
> I have a P0420 on a 2015 Honda Accord 2.4L. Customer says it comes back after clearing. Is this always a bad cat?

**AI explains:**
- How the PCM actually determines catalyst efficiency (rear O2 switching rate vs front)
- Common misdiagnoses (exhaust leaks, O2 sensor bias, fuel trim issues)
- How to verify cat efficiency with a scope pattern
- Why upstream issues cause this code (rich condition damages catalyst over time)
- The difference between a worn cat and a poisoned cat

**Why this is powerful:** You understand the diagnostic logic, not just the code definition.

---

## Multi-System Interaction Problems

**Modern vehicles have systems that interact in complex ways. AI can trace those connections.**

### Example: A/C Affects Idle

**Your question:**
> 2019 Chevy Equinox 1.5T. A/C compressor cycles on and engine almost stalls, then recovers. Idle is rough with A/C on. No codes.

**AI traces the interaction:**
- How PCM should compensate for A/C load (idle air control, electronic throttle)
- What sensors feed into that compensation (A/C pressure, A/C request signal, engine load)
- Possible causes: weak idle learn, carbon buildup on throttle body, A/C pressure switch signal issue
- How to test: commanded idle speed vs actual with A/C on
- Known issues for this symptom on this platform

**Why this is powerful:** You see the whole system interaction, not just individual components.

---

## Wiring and Electrical Diagnosis

**Describe electrical symptoms and get circuit analysis.**

### Example: Parasitic Draw

**Your question:**
> 2017 Jeep Grand Cherokee. Battery dead every few days. I pulled fuses one by one and the draw drops when I pull the IOD fuse. That's like 30 circuits. How do I narrow it down?

**AI provides:**
- Strategy for isolating the circuit (module sleep timer considerations)
- Common culprits on this platform (radio, HVAC module, BCM)
- How to use current clamp vs fuse pulling (why waiting 45 minutes matters)
- Which modules have known issues staying awake
- How to interpret network activity during sleep mode

---

## Explaining the "Why" Behind Failures

**Don't just identify what failed—understand why it failed.**

### Example: Repeat Alternator Failure

**Your question:**
> 2016 Ram 1500 5.7 Hemi. Third alternator in 2 years. Each one tests bad after 6-8 months. What's killing them?

**AI investigates:**
- What actually fails in alternators (diodes, bearings, regulator)
- Root causes for repeat failure: loose/corroded ground, battery internal short drawing excessive current, undersized battery for accessories
- How to test charging system under load
- Checking for AC ripple that indicates diode failure pattern
- Aftermarket alternator quality issues vs OE

**Why this is powerful:** You solve the actual problem instead of replacing parts repeatedly.

---

## Sensor Plausibility and Rationality

**Understand how the PCM decides if sensor data makes sense.**

### Example: MAP/MAF Correlation

**Your question:**
> 2014 VW Jetta 1.8T. P0106 MAP sensor performance. I replaced the MAP sensor and code came back. Sensor tests fine with vacuum pump.

**AI explains:**
- How PCM cross-checks MAP against MAF and throttle position
- Why a "good" sensor can still set this code (intake leak, MAF contamination)
- The calculated vs actual airflow comparison logic
- Boost leak detection strategy on turbocharged engines
- How to smoke test the intake system properly

---

## Transmission and Driveline

**Complex transmission diagnostics simplified.**

### Example: Shudder on Light Acceleration

**Your question:**
> 2018 GMC Sierra 1500 with 8-speed. Shudder/vibration between 25-45 mph on light acceleration. Goes away if I accelerate harder. Feels like driving over rumble strips.

**AI identifies:**
- Torque converter clutch shudder pattern (classic TCC slip-stick)
- Fluid condition and how degraded ATF causes this
- Known service bulletins for this transmission
- Why light load reveals it (TCC applied, low clamp pressure)
- Verification procedure before recommending converter replacement

---

## Training and Explaining to Customers

**Use AI to explain complex repairs in customer-friendly terms.**

### Example:
> Explain to a customer why their VVT solenoid failure is related to oil change intervals, in simple terms they'll understand.

**AI generates a clear, non-technical explanation** that helps the customer understand the repair and why maintenance matters, without talking down to them.

---

## Pattern Recognition Across Vehicles

**AI remembers patterns across thousands of vehicles and years.**

### Example:
> I've seen three 2015-2017 Hyundai Sonatas with engine knock this month. Is there a known issue?

**AI connects the dots:**
- Theta II engine bearing issues and class action
- How to identify affected VINs
- Warranty extension programs
- Proper documentation for goodwill claims

---

## CAN Bus and Network Diagnostics

**Understand how modules communicate and what happens when they don't.**

### Example: Multiple Warning Lights After Battery Change

**Your question:**
> 2020 BMW X3. Customer replaced battery at home. Now has ABS, traction control, and parking brake warnings. Battery tests fine.

**AI explains:**
- Why BMW needs battery registration (IBS sensor calibration)
- How the new battery's different capacity affects charging strategy
- Which modules need to relearn after power loss
- The reset procedure and whether dealer scan tool is required
- What happens if you skip registration (overcharging, premature failure)

---

## ADAS Systems and Calibration

**Navigate the complexity of modern driver assistance systems.**

### Example: Windshield Replacement Calibration

**Your question:**
> Customer needs windshield replaced on 2021 Toyota RAV4 with lane departure and adaptive cruise. What calibration is needed?

**AI explains:**
- Static vs dynamic calibration requirements
- Target board setup dimensions and positioning
- OEM vs aftermarket calibration procedures
- What happens if you skip calibration (liability, safety)
- Pre-scan and post-scan documentation requirements

---

## Best Practices

1. **Be specific with year/make/model/engine** — The AI gives much better answers with exact vehicle info
2. **Describe symptoms completely** — include when it happens, what makes it better/worse, any recent work
3. **Ask follow-up questions** — dig deeper if the first answer doesn't solve it
4. **Upload photos** — diagnostic screenshots, scan tool data, or component photos help the AI understand the situation
5. **Ask "why"** — understanding the system helps you diagnose faster next time

---

## The AI Advantage

What makes AI different from Google or forums:
- **Reasoning, not just search** — AI thinks through the diagnostic logic
- **No outdated posts** — you're not reading a forum thread from 2009
- **Specific to YOUR vehicle** — not generic advice
- **Asks clarifying questions** — if more info would help, AI asks
- **Explains the why** — teaches you, not just tells you
- **System-level thinking** — connects symptoms across multiple systems
