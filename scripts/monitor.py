#!/usr/bin/env python3
"""
Script to monitor LogiChain system
"""
import os
import sys
import argparse
import json
import time
import logging
import psutil
import docker
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import subprocess

class SystemMonitor:
    def __init__(self, log_file: str = "data/logs/monitor.log"):
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize Docker client
        self.docker = docker.from_env()
        
        # Load environment variables
        self.load_env()
    
    def load_env(self):
        """Load environment variables"""
        self.env = {}
        env_file = Path("config/.env.production")
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        self.env[key.strip()] = value.strip()
    
    def check_system_resources(self) -> Dict[str, float]:
        """Check system resource usage"""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent
        }
    
    def check_docker_containers(self) -> List[Dict[str, Any]]:
        """Check Docker container status"""
        containers = []
        
        for container in self.docker.containers.list(all=True):
            stats = container.stats(stream=False)
            
            # Calculate CPU usage
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = 0.0
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * 100.0
            
            # Calculate memory usage
            memory_usage = stats["memory_stats"]["usage"]
            memory_limit = stats["memory_stats"]["limit"]
            memory_percent = (memory_usage / memory_limit) * 100.0
            
            containers.append({
                "name": container.name,
                "status": container.status,
                "cpu_percent": round(cpu_percent, 2),
                "memory_percent": round(memory_percent, 2),
                "restarts": container.attrs["RestartCount"]
            })
        
        return containers
    
    def check_api_health(self) -> Dict[str, bool]:
        """Check API endpoints health"""
        endpoints = {
            "api": f"http://localhost:{self.env.get('API_PORT', 5000)}/health",
            "web": f"http://localhost:{self.env.get('WEB_PORT', 8080)}/health",
            "integrated": f"http://localhost:{self.env.get('INTEGRATED_PORT', 8000)}/health"
        }
        
        results = {}
        for name, url in endpoints.items():
            try:
                response = requests.get(url, timeout=5)
                results[name] = response.status_code == 200
            except:
                results[name] = False
        
        return results
    
    def check_blockchain_status(self) -> Dict[str, Any]:
        """Check blockchain status"""
        try:
            response = requests.get(
                f"http://localhost:{self.env.get('API_PORT', 5000)}/v1/status",
                timeout=5
            )
            return response.json()
        except:
            return {
                "error": "Failed to get blockchain status",
                "is_healthy": False
            }
    
    def check_logs(self, hours: int = 1) -> Dict[str, List[str]]:
        """Check logs for errors"""
        log_dir = Path("data/logs")
        results = {}
        
        for log_file in log_dir.glob("*.log"):
            errors = []
            try:
                # Get logs from last N hours
                cmd = f"grep -i 'error\\|exception' {log_file} | grep -i '{datetime.now() - timedelta(hours=hours)}'"
                output = subprocess.check_output(cmd, shell=True)
                errors = output.decode().splitlines()
            except subprocess.CalledProcessError:
                pass
            
            results[log_file.name] = errors
        
        return results
    
    def check_ssl_certificates(self) -> Dict[str, Any]:
        """Check SSL certificate status"""
        cert_file = Path("data/ssl/cert.pem")
        if not cert_file.exists():
            return {"error": "Certificate not found"}
        
        try:
            cmd = f"openssl x509 -enddate -noout -in {cert_file}"
            output = subprocess.check_output(cmd, shell=True)
            expiry = output.decode().split('=')[1].strip()
            expiry_date = datetime.strptime(expiry, "%b %d %H:%M:%S %Y %Z")
            days_left = (expiry_date - datetime.now()).days
            
            return {
                "expires": expiry,
                "days_left": days_left,
                "is_valid": days_left > 0
            }
        except:
            return {"error": "Failed to check certificate"}
    
    def check_disk_space(self) -> Dict[str, Any]:
        """Check disk space usage"""
        paths = {
            "blockchain": "data/blockchain",
            "contracts": "data/contracts",
            "logs": "data/logs",
            "backups": "backups"
        }
        
        results = {}
        for name, path in paths.items():
            if os.path.exists(path):
                usage = psutil.disk_usage(path)
                results[name] = {
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent
                }
        
        return results
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate monitoring report"""
        return {
            "timestamp": datetime.now().isoformat(),
            "system_resources": self.check_system_resources(),
            "docker_containers": self.check_docker_containers(),
            "api_health": self.check_api_health(),
            "blockchain_status": self.check_blockchain_status(),
            "ssl_certificates": self.check_ssl_certificates(),
            "disk_space": self.check_disk_space()
        }
    
    def monitor(self, interval: int = 300):
        """Continuous monitoring"""
        while True:
            try:
                report = self.generate_report()
                
                # Check for critical issues
                critical_issues = []
                
                # Check system resources
                if report["system_resources"]["cpu_percent"] > 90:
                    critical_issues.append("High CPU usage")
                if report["system_resources"]["memory_percent"] > 90:
                    critical_issues.append("High memory usage")
                if report["system_resources"]["disk_percent"] > 90:
                    critical_issues.append("High disk usage")
                
                # Check container status
                for container in report["docker_containers"]:
                    if container["status"] != "running":
                        critical_issues.append(
                            f"Container {container['name']} is {container['status']}"
                        )
                    if container["restarts"] > 5:
                        critical_issues.append(
                            f"Container {container['name']} has high restart count"
                        )
                
                # Check API health
                for api, is_healthy in report["api_health"].items():
                    if not is_healthy:
                        critical_issues.append(f"{api} API is unhealthy")
                
                # Check SSL certificate
                ssl_status = report["ssl_certificates"]
                if "days_left" in ssl_status and ssl_status["days_left"] < 30:
                    critical_issues.append(
                        f"SSL certificate expires in {ssl_status['days_left']} days"
                    )
                
                # Log issues
                if critical_issues:
                    self.logger.warning(
                        "Critical issues found:\n" + "\n".join(critical_issues)
                    )
                else:
                    self.logger.info("System healthy")
                
                # Save report
                report_file = Path("data/logs/monitor_report.json")
                with open(report_file, "w") as f:
                    json.dump(report, f, indent=2)
                
            except Exception as e:
                self.logger.error(f"Monitoring error: {str(e)}")
            
            time.sleep(interval)

def main():
    parser = argparse.ArgumentParser(description="Monitor LogiChain system")
    parser.add_argument('--interval', type=int, default=300,
                      help="Monitoring interval in seconds")
    parser.add_argument('--log-file', default="data/logs/monitor.log",
                      help="Log file path")
    parser.add_argument('--once', action='store_true',
                      help="Run once and exit")
    
    args = parser.parse_args()
    
    monitor = SystemMonitor(args.log_file)
    
    if args.once:
        report = monitor.generate_report()
        print(json.dumps(report, indent=2))
    else:
        monitor.monitor(args.interval)

if __name__ == "__main__":
    main() 