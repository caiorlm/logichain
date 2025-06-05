#!/usr/bin/env python3
"""
Script to generate keys and certificates for LogiChain
"""
import os
import sys
import argparse
from pathlib import Path
import secrets
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
from cryptography.hazmat.primitives import serialization
from cryptography.x509 import (
    Name, NameAttribute, NameOID, CertificateBuilder,
    SubjectAlternativeName, DNSName, IPAddress
)
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.asymmetric import ec
from datetime import datetime, timedelta
import ipaddress

class KeyGenerator:
    def __init__(self, output_dir: str = "data/keys"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_rsa_key(self, name: str, key_size: int = 2048) -> tuple:
        """Generate RSA key pair"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size
        )
        
        public_key = private_key.public_key()
        
        # Save private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Save public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        private_path = self.output_dir / f"{name}_private.pem"
        public_path = self.output_dir / f"{name}_public.pem"
        
        with open(private_path, "wb") as f:
            f.write(private_pem)
        
        with open(public_path, "wb") as f:
            f.write(public_pem)
        
        return private_key, public_key
    
    def generate_ec_key(self, name: str, curve=ec.SECP256K1()) -> tuple:
        """Generate EC key pair"""
        private_key = ec.generate_private_key(curve)
        public_key = private_key.public_key()
        
        # Save private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Save public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        private_path = self.output_dir / f"{name}_private.pem"
        public_path = self.output_dir / f"{name}_public.pem"
        
        with open(private_path, "wb") as f:
            f.write(private_pem)
        
        with open(public_path, "wb") as f:
            f.write(public_pem)
        
        return private_key, public_key
    
    def generate_node_keys(self, node_type: str):
        """Generate keys for a specific node type"""
        return self.generate_ec_key(f"{node_type}_node")
    
    def generate_ssl_cert(self, 
                         common_name: str,
                         dns_names: list = None,
                         ip_addresses: list = None,
                         key_size: int = 2048,
                         days_valid: int = 365):
        """Generate SSL certificate"""
        # Generate key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size
        )
        
        # Create certificate subject
        subject = Name([
            NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "SP"),
            NameAttribute(NameOID.LOCALITY_NAME, "Sao Paulo"),
            NameAttribute(NameOID.ORGANIZATION_NAME, "LogiChain"),
            NameAttribute(NameOID.COMMON_NAME, common_name)
        ])
        
        # Prepare alternative names
        alt_names = []
        if dns_names:
            alt_names.extend([DNSName(name) for name in dns_names])
        if ip_addresses:
            alt_names.extend([IPAddress(ipaddress.ip_address(ip)) 
                            for ip in ip_addresses])
        
        # Create certificate
        builder = CertificateBuilder()
        builder = builder.subject_name(subject)
        builder = builder.issuer_name(subject)  # Self-signed
        builder = builder.not_valid_before(datetime.utcnow())
        builder = builder.not_valid_after(
            datetime.utcnow() + timedelta(days=days_valid)
        )
        builder = builder.serial_number(secrets.randbits(64))
        builder = builder.public_key(private_key.public_key())
        
        if alt_names:
            builder = builder.add_extension(
                SubjectAlternativeName(alt_names),
                critical=False
            )
        
        certificate = builder.sign(
            private_key,
            hashes.SHA256()
        )
        
        # Save certificate and private key
        cert_path = self.output_dir / f"{common_name}.crt"
        key_path = self.output_dir / f"{common_name}.key"
        
        with open(cert_path, "wb") as f:
            f.write(certificate.public_bytes(serialization.Encoding.PEM))
        
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        return certificate, private_key

def main():
    parser = argparse.ArgumentParser(description="Generate keys for LogiChain")
    parser.add_argument('--output-dir', default="data/keys",
                      help="Output directory for keys")
    parser.add_argument('--node-types', nargs='+',
                      default=["validator", "executor", "establishment"],
                      help="Node types to generate keys for")
    parser.add_argument('--ssl-common-name', default="logichain.local",
                      help="Common name for SSL certificate")
    parser.add_argument('--ssl-dns-names', nargs='+',
                      default=["localhost", "logichain.local"],
                      help="DNS names for SSL certificate")
    parser.add_argument('--ssl-ip-addresses', nargs='+',
                      default=["127.0.0.1"],
                      help="IP addresses for SSL certificate")
    
    args = parser.parse_args()
    
    generator = KeyGenerator(args.output_dir)
    
    print("Generating node keys...")
    for node_type in args.node_types:
        print(f"Generating keys for {node_type} node")
        generator.generate_node_keys(node_type)
    
    print("\nGenerating SSL certificate...")
    generator.generate_ssl_cert(
        common_name=args.ssl_common_name,
        dns_names=args.ssl_dns_names,
        ip_addresses=args.ssl_ip_addresses
    )
    
    print("\nKey generation complete!")
    print(f"Keys and certificates saved in: {args.output_dir}")
    print("\nIMPORTANT: Backup these keys securely and never commit them to version control!")

if __name__ == "__main__":
    main() 