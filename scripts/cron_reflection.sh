#!/bin/bash
# Daily reflection - consolidate memory
cd /home/agent/.openclaw/workspace
python3 -c "
import sys
sys.path.insert(0, '/home/agent/.openclaw/workspace/scripts')
from brain import brain
brain.optimize()
brain.set_context('Daily reflection complete')
print('Reflection done')
" >> /home/agent/.openclaw/workspace/memory/cron_reflection.log 2>&1
