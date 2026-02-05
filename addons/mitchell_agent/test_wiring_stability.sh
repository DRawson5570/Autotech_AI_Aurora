#!/bin/bash
# Wiring Diagram Stability Test
# Tests whether Gemini consistently includes images from tool results

NUM_TESTS=${1:-5}
DELAY=${2:-10}
QUERY="Show me ac wiring diagram for 2014 chevy cruze 1.4 lt"

# Results file
RESULTS_FILE="/tmp/wiring_stability_$(date +%Y%m%d_%H%M%S).log"
echo "=== Wiring Diagram Stability Test ===" | tee $RESULTS_FILE
echo "Tests: $NUM_TESTS, Delay: ${DELAY}s" | tee -a $RESULTS_FILE
echo "Query: $QUERY" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

# Counters
PASS=0
FAIL=0
HALLUCINATE=0

cd /home/drawson/autotech_ai

for i in $(seq 1 $NUM_TESTS); do
    echo "--- Test $i of $NUM_TESTS at $(date +%H:%M:%S) ---" | tee -a $RESULTS_FILE
    
    # Run test and capture output
    OUTPUT=$(timeout 180 conda run -n open-webui python addons/mitchell_agent/test_chat_e2e.py --query "$QUERY" 2>&1)
    
    # Check for images in response
    if echo "$OUTPUT" | grep -q '/static/mitchell/diagram'; then
        echo "✅ PASS - Images included" | tee -a $RESULTS_FILE
        ((PASS++))
    elif echo "$OUTPUT" | grep -qi "impossible\|cannot provide\|don't have access"; then
        echo "❌ FAIL - Gemini HALLUCINATED (said impossible)" | tee -a $RESULTS_FILE
        ((HALLUCINATE++))
        ((FAIL++))
    elif echo "$OUTPUT" | grep -q "DATA UNVERIFIED"; then
        echo "❌ FAIL - Only DATA UNVERIFIED, no images" | tee -a $RESULTS_FILE
        ((FAIL++))
    else
        echo "⚠️ UNKNOWN - Check output" | tee -a $RESULTS_FILE
        ((FAIL++))
    fi
    
    # Save response snippet
    echo "$OUTPUT" | grep -A5 -- "--- LLM Response ---" | head -10 >> $RESULTS_FILE
    echo "" >> $RESULTS_FILE
    
    # For UNKNOWN, save more context
    if [ $? -ne 0 ] || ! echo "$OUTPUT" | grep -q '!\[.*\](/static/mitchell/'; then
        echo "DEBUG OUTPUT:" >> $RESULTS_FILE
        echo "$OUTPUT" | tail -30 >> $RESULTS_FILE
        echo "---" >> $RESULTS_FILE
    fi
    
    # Delay between tests (except last)
    if [ $i -lt $NUM_TESTS ]; then
        echo "Sleeping ${DELAY}s..." 
        sleep $DELAY
    fi
done

echo "" | tee -a $RESULTS_FILE
echo "=== SUMMARY ===" | tee -a $RESULTS_FILE
echo "Total: $NUM_TESTS" | tee -a $RESULTS_FILE
echo "Pass:  $PASS ($(( PASS * 100 / NUM_TESTS ))%)" | tee -a $RESULTS_FILE
echo "Fail:  $FAIL ($(( FAIL * 100 / NUM_TESTS ))%)" | tee -a $RESULTS_FILE
echo "  - Hallucinations: $HALLUCINATE" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE
echo "Results saved to: $RESULTS_FILE"

# Exit with error if any failures
[ $FAIL -eq 0 ]
