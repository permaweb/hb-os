#!/usr/bin/env python3
"""
Node API functions for interacting with the node endpoints.
These functions provide a Python equivalent of the JavaScript API.
"""

import requests
import json
import base64
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend

# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    DEBUG = "\033[97m"  # Dark cyan for debug messages
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

def print_error(message):
    """Print an error message in red"""
    print(f"{Colors.RED}{Colors.BOLD}ERROR:{Colors.RESET} {message}")

def print_success(message):
    """Print a success message in green"""
    print(f"{Colors.GREEN}SUCCESS:{Colors.RESET} {message}")

def print_warning(message):
    """Print a warning message in yellow"""
    print(f"{Colors.YELLOW}WARNING:{Colors.RESET} {message}")

def print_info(message):
    """Print an info message in cyan"""
    print(f"{Colors.CYAN}INFO:{Colors.RESET} {message}")

def print_debug(message):
    """Print a debug message in dark cyan"""
    print(f"{Colors.DEBUG}DEBUG:{Colors.RESET} {message}")

def print_command(message):
    """Print a command in magenta"""
    print(f"{Colors.MAGENTA}COMMAND:{Colors.RESET} {message}")

def print_step(message):
    """Print a step or action in blue"""
    print(f"{Colors.BLUE}{Colors.BOLD}===== {message} ====={Colors.RESET}")

def get_node_info(node_url):
    """
    Get node information including its ID
    
    Args:
        node_url: URL of the node
        
    Returns:
        dict: A dictionary with id and location of the node
    """
    print_command(f"~meta@1.0/info/address")
    print_info(f"Path: {node_url}/~meta@1.0/info/address")
    try:
        response = requests.get(f"{node_url}/~meta@1.0/info/address")
        response_body = response.text
        if response.status_code == 200:
            print_success(response_body)
        else:
            print_warning(f"Error getting node info: {response.status_code}")
            print_warning(response_body)
        node_info = {"id": response_body, "location": node_url}
        print_info(f"Node info:\n{json.dumps(node_info, indent=4)}")
        return node_info
    except requests.RequestException as e:
        print_error(f"Error getting node info: {e}")
        return {"id": None, "location": node_url}

def get_node_process_routes(node_url):
    """
    Get node process routes
    
    Args:
        node_url: URL of the node
    """
    print_command(f"~router@1.0/now/routes")
    print_info(f"Path: {node_url}/router~node-process@1.0/now/routes")
    try:
        response = requests.get(f"{node_url}/router~node-process@1.0/now/routes")
        response_body = response.text
        if response.status_code == 200:
            print_success(response_body)
        else:
            print_warning(f"Error getting node process routes: {response.status_code}")
            print_warning(response_body)
    except requests.RequestException as e:
        print_error(f"Error getting node process routes: {e}")

def register_node(node_url):
    """
    Register a node
    
    Args:
        node_url: URL of the node
    """
    print_command(f"~router@1.0/register")
    print_info(f"Path: {node_url}/~router@1.0/register")
    try:
        response = requests.get(f"{node_url}/~router@1.0/register")
        response_body = response.text
        if response.status_code == 200:
            print_success(response_body)
        else:
            print_warning(f"Error registering node: {response.status_code}")
            print_warning(response_body)
    except requests.RequestException as e:
        print_error(f"Error registering node: {e}")

def meta_post(node_url, config_content, device="json@1.0"):
    """
    Post configuration to meta info
    
    Args:
        node_url: URL of the node
        config_content: Configuration content to post
        device: Codec device, defaults to "json@1.0"
    """
    print_command(f"~meta@1.0/info")
    print_info(f"Path: {node_url}/~meta@1.0/info")
    print_info(f"Device: {device}")
    try:
        headers = {"codec-device": device}
        response = requests.post(
            f"{node_url}/~meta@1.0/info", 
            headers=headers, 
            data=json.dumps(config_content)
        )
        response_body = response.text
        if response.status_code == 200:
            print_success(response_body)
        else:
            print_warning(f"Error posting to meta: {response.status_code}")
            print_warning(response_body)
    except requests.RequestException as e:
        print_error(f"Error posting to meta: {e}") 
        
def initialize_greenzone(node_url):
    """
    Initialize greenzone for a node
    
    Args:
        node_url: URL of the node
        
    Returns:
        response: The response from the greenzone init request
    """
    print_command(f"~greenzone@1.0/init")
    print_info(f"Path: {node_url}/~greenzone@1.0/init")
    try:
        response = requests.get(f"{node_url}/~greenzone@1.0/init")
        response_body = response.text
        if response.status_code == 200:
            print_success(response_body)
        else:
            print_warning(f"Error initializing greenzone: {response.status_code}")
            print_warning(response_body)
        return response
    except requests.RequestException as e:
        print_error(f"Error initializing greenzone: {e}")
        return None

def join_node(node_url, peer_location, peer_id, adopt_config=True):
    """
    Send a join request from one node to another
    
    Args:
        node_url: URL of the node
        peer_location: URL of the peer node
        peer_id: ID of the peer node
        adopt_config: Whether to adopt the peer's configuration
        
    Returns:
        response: The response from the join request
    """
    print_command(f"~greenzone@1.0/join")
    print_info(f"Path: {node_url}/~greenzone@1.0/join")
    print_info(f"Peer Location: {peer_location}")
    print_info(f"Peer ID: {peer_id}")
    print_info(f"Adopt Config: {adopt_config}")
    try:
        headers = {
            'peer-location': peer_location,
            'peer-id': peer_id,
            'adopt-config': str(adopt_config).lower()
        }
        print_info(f"Join Request Headers: {headers}")
        
        response = requests.get(
            f"{node_url}/~greenzone@1.0/join",
            headers=headers
        )
        response_body = response.text
        if response.status_code == 200:
            print_success(response_body)
        else:
            print_warning(f"Error joining node: {response.status_code}")
            print_warning(response_body)
        return response
    except requests.RequestException as e:
        print_error(f"Error joining node: {e}")
        return None

def become_node(node_url, peer_location, peer_id):
    """
    Send a become request from one node to another
    
    Args:
        node_url: URL of the node
        peer_location: URL of the peer node
        peer_id: ID of the peer node
        
    Returns:
        response: The response from the become request
    """
    print_command(f"~greenzone@1.0/become")
    print_info(f"Path: {node_url}/~greenzone@1.0/become")
    print_info(f"Peer Location: {peer_location}")
    print_info(f"Peer ID: {peer_id}")
    try:
        headers = {
            'peer-location': peer_location,
            'peer-id': peer_id
        }
        
        response = requests.get(
            f"{node_url}/~greenzone@1.0/become",
            headers=headers
        )
        response_body = response.text
        if response.status_code == 200:
            print_success(response_body)
        else:
            print_warning(f"Error becoming node: {response.status_code}")
            print_warning(response_body)
        return response
    except requests.RequestException as e:
        print_error(f"Error becoming node: {e}")
        return None 

def mount(node_url):
    """
    Mount a volume
    
    Args:
        node_url: URL of the node
    """
    print_command(f"~volume@1.0/mount")
    print_info(f"Path: {node_url}/~volume@1.0/mount")
    try:
        response = requests.get(
            f"{node_url}/~volume@1.0/mount",
        )
        response_body = response.text
        print_info(f"Status: {response.status_code}")
        if response.status_code == 200:
            print_success(f"Body: {response_body}")
        else:
            print_warning(f"Error mounting volume: {response.status_code}")
            print_warning(f"Body: {response_body}")
        return response
    except requests.RequestException as e:
        print_error(f"Error mounting volume: {e}")
        return None

def get_volume_public_key(node_url):
    """
    Retrieves the node's public key for secure key exchange
    This allows users to securely exchange encryption keys by first encrypting 
    their volume key with the node's public key
    
    Args:
        node_url: URL of the node
        
    Returns:
        str: The node's public key
    """
    print_command(f"~volume@1.0/public_key")
    print_info(f"Path: {node_url}/~volume@1.0/public_key")
    try:
        response = requests.get(f"{node_url}/~volume@1.0/public_key")
        if response.status_code == 200:
            public_key = response.headers.get('public_key')
            print_success(f"Public key: {public_key}")
            return public_key
        else:
            print_warning(f"Error getting volume public key: {response.status_code}")
            print_warning(response.text)
            return None
    except requests.RequestException as e:
        print_error(f"Error getting volume public key: {e}")
        raise

def encrypt_volume_secret(public_key_base64, secret):
    """
    Encrypts a secret with a node's public key and returns the base64-encoded result
    
    Args:
        public_key_base64: The base64-encoded DER-format public key from get_volume_public_key()
        secret: The secret to encrypt (e.g., volume encryption key)
        
    Returns:
        str: Base64 encoded encrypted secret
    """
    try:
        # Decode the base64-encoded DER format key
        der_key = base64.b64decode(public_key_base64)
        
        # Load the DER key
        public_key = serialization.load_der_public_key(
            der_key,
            backend=default_backend()
        )
        
        # Encrypt with the public key
        encrypted = public_key.encrypt(
            secret.encode() if isinstance(secret, str) else secret,
            padding.PKCS1v15()
        )
        
        # Return base64 encoded encrypted data
        return base64.b64encode(encrypted).decode()
    except Exception as e:
        print_error(f"Error encrypting with volume key: {e}")
        raise 
        
