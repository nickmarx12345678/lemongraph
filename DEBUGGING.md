# LemonGraph Debugging Guide

## Worker Stack Trace Dumping

When workers appear to be stuck or hanging, you can dump their stack traces to identify exactly where they're blocked.

### Signal Handlers

Each worker process installs signal handlers for:

- **SIGUSR1** - Dump stack trace (non-fatal, worker continues)
- **SIGUSR2** - Dump stack trace (non-fatal, worker continues)  
- **SIGTERM** - Dump stack trace and exit worker
- **SIGINT** - Dump stack trace and exit worker

### Usage

#### 1. Find Worker PIDs

```bash
# Find all LemonGraph processes
ps aux | grep -E 'LemonGraph|lemongraph' | grep -v grep

# Or use pgrep
pgrep -f lemongraph
```

#### 2. Dump Stack Traces

**Non-fatal dump (worker continues running):**
```bash
kill -USR1 <worker_pid>
```

**Fatal dump (worker exits after dumping):**
```bash
kill -TERM <worker_pid>
```

**Using the helper script:**
```bash
# Non-fatal dump
./scripts/dump_worker_stacks USR1 12345

# Fatal dump  
./scripts/dump_worker_stacks TERM 12345 12346

# Default (USR1)
./scripts/dump_worker_stacks 12345
```

#### 3. Container/Docker Usage

**For containerized deployments:**
```bash
# Find container
docker ps | grep lemongraph

# Send signal to specific worker inside container
docker exec <container_id> kill -USR1 <worker_pid>

# Or kill the entire container (will dump all worker stacks)
docker kill -s TERM <container_id>
```

### Stack Trace Output

Stack traces appear in your LemonGraph logs with this format:

```
================================================================================
worker(12345): Received SIGUSR1 - dumping stack traces for all threads
================================================================================
Thread 140234567890 (MainThread):
----------------------------------------
  File "/path/to/LemonGraph/httpd.py", line 380, in worker
    self.process(req, res)
  File "/path/to/LemonGraph/server/__init__.py", line 245, in process_query
    results = self.collection.query(query_string)
  File "/path/to/LemonGraph/collection.py", line 156, in query
    return self.graph.query(query)
  [... more stack frames ...]

================================================================================
worker(12345): Stack trace dump complete
================================================================================
```

### Common Hang Locations

Look for workers stuck in:

- **Database operations** - `collection.py`, `graph.py`
- **Network I/O** - `socket.recv()`, `socket.send()`
- **File I/O** - File read/write operations
- **Lock contention** - `threading.Lock.acquire()`
- **External API calls** - HTTP requests, external services

### Troubleshooting Tips

1. **Multiple workers stuck in same location** = Likely a shared resource bottleneck
2. **Workers stuck in different locations** = Likely individual request issues  
3. **Workers stuck in I/O operations** = Network/disk performance issues
4. **Workers stuck in database code** = Database lock contention or slow queries

### Automation

You can automate stack dumping when workers appear stuck:

```bash
#!/bin/bash
# Monitor and dump stacks for long-running workers
while true; do
    # Find workers running longer than 5 minutes
    long_workers=$(ps -eo pid,etime,cmd | grep lemongraph | awk '$2 ~ /[0-9][0-9]:[0-9][0-9]/ {print $1}')
    
    for pid in $long_workers; do
        echo "Dumping stack for long-running worker $pid"
        kill -USR1 $pid
    done
    
    sleep 300  # Check every 5 minutes
done
```
