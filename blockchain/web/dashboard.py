from flask import Flask, render_template, jsonify
from datetime import datetime
import time
from pathlib import Path
from typing import Dict

app = Flask(__name__)

# Ensure templates directory exists
template_dir = Path(__file__).parent / "templates"
template_dir.mkdir(parents=True, exist_ok=True)

# Create base template
base_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Blockchain Monitor</title>
    <style>
        body { font-family: Arial; margin: 20px; }
        .status { padding: 10px; margin: 10px; border-radius: 5px; }
        .online { background: #d4edda; }
        .offline { background: #fff3cd; }
        .error { background: #f8d7da; }
        .card { border: 1px solid #ddd; padding: 15px; margin: 10px; border-radius: 5px; }
        .button { 
            background: #007bff; 
            color: white; 
            padding: 10px 20px; 
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
    </style>
    <script>
        function updateStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('mode').textContent = data.mode;
                    document.getElementById('pending').textContent = data.pending_operations;
                    document.getElementById('last_sync').textContent = data.last_sync;
                    document.getElementById('status').className = 
                        'status ' + (data.mode === 'ONLINE' ? 'online' : 'offline');
                });
        }
        
        function syncNow() {
            fetch('/api/sync', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                    updateStatus();
                });
        }
        
        // Update every 5 seconds
        setInterval(updateStatus, 5000);
    </script>
</head>
<body>
    <h1>Blockchain Monitor</h1>
    
    <div id="status" class="status">
        <h2>Network Status</h2>
        <p>Mode: <span id="mode">-</span></p>
        <p>Pending Operations: <span id="pending">-</span></p>
        <p>Last Sync: <span id="last_sync">-</span></p>
    </div>
    
    <div class="card">
        <h2>Security Status</h2>
        <p>Recent Signatures: <span id="signatures">-</span></p>
        <p>Chain Health: <span id="health">-</span></p>
    </div>
    
    <div class="card">
        <h2>Actions</h2>
        <button class="button" onclick="syncNow()">Sync Now</button>
    </div>
</body>
</html>
"""

# Save template
(template_dir / "index.html").write_text(base_template)

class BlockchainMonitor:
    def __init__(self):
        self.last_sync = time.time()
        self.mode = "OFFLINE"
        self.pending_ops = 0
        
    def get_status(self) -> Dict:
        return {
            "mode": self.mode,
            "pending_operations": self.pending_ops,
            "last_sync": datetime.fromtimestamp(self.last_sync).isoformat()
        }
        
    def trigger_sync(self) -> Dict:
        try:
            # Implement actual sync logic here
            self.last_sync = time.time()
            return {"success": True, "message": "Sync completed successfully"}
        except Exception as e:
            return {"success": False, "message": f"Sync failed: {str(e)}"}

# Create monitor instance
monitor = BlockchainMonitor()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def status():
    return jsonify(monitor.get_status())

@app.route('/api/sync', methods=['POST'])
def sync():
    return jsonify(monitor.trigger_sync())

def start_dashboard(host='localhost', port=8000):
    app.run(host=host, port=port)

if __name__ == '__main__':
    start_dashboard() 