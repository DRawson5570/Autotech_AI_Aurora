cd /home/drawson/autotech_ai/addons/predictive_diagnostics && nohup conda run -n chrono_test python chrono_simulator/batch_generator.py --samples 20000 --workers 8
sleep 3 && tail -20 /tmp/batch_gen.log

