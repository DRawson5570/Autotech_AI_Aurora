python stress_test_model.py --url http://127.0.0.1:11434/api/generate --model gpt-oss:120b --prompt "Tell me a 20 word joke.  Don't worry about the exact word count because it's just a test." --baseline

echo "Running 20 concurrent users"

python stress_test_model.py --url http://127.0.0.1:11434/api/generate --model gpt-oss:120b --prompt "Tell me a 20 word joke.  Don't worry about the exact word count because it's just a test." --requests 100 --concurrency 20
