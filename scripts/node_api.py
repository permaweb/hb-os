#!/usr/bin/env python3
"""
Node API functions for interacting with the node endpoints.
These functions provide a Python equivalent of the JavaScript API.
"""

import requests
import json

# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

def print_error(message):
    """Print an error message in red"""
    print(f"{Colors.RED}{Colors.BOLD}ERROR: {message}{Colors.RESET}")

def print_success(message):
    """Print a success message in green"""
    print(f"{Colors.GREEN}SUCCESS: {Colors.RESET}{message}")

def print_warning(message):
    """Print a warning message in yellow"""
    print(f"{Colors.YELLOW}WARNING: {message}{Colors.RESET}")

def print_info(message):
    """Print an info message in cyan"""
    print(f"{Colors.CYAN}INFO: {Colors.RESET}{message}")

def print_command(message):
    """Print a command in magenta"""
    print(f"{Colors.MAGENTA}COMMAND: {Colors.RESET}{message}")

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
    print_command(f"get_node_info: {node_url}")
    try:
        response = requests.get(f"{node_url}/~meta@1.0/info/address")
        response_body = response.text
        print_info(f"Status: {response.status_code}")
        print_info(f"Body: {response_body}")
        return {"id": response_body, "location": node_url}
    except requests.RequestException as e:
        print_error(f"Error getting node info: {e}")
        return {"id": None, "location": node_url}

def get_node_process_routes(node_url):
    """
    Get node process routes
    
    Args:
        node_url: URL of the node
    """
    print_command(f"get_node_process_routes: {node_url}")
    try:
        response = requests.get(f"{node_url}/router~node-process@1.0/now/routes")
        response_body = response.text
        print_info(f"Status: {response.status_code}")
        print_info(f"Body: {response_body}")
    except requests.RequestException as e:
        print_error(f"Error getting node process routes: {e}")

def register_node(node_url):
    """
    Register a node
    
    Args:
        node_url: URL of the node
    """
    print_command(f"register_node: {node_url}")
    try:
        response = requests.get(f"{node_url}/~router@1.0/register")
        response_body = response.text
        print_info(f"Status: {response.status_code}")
        print_info(f"Body: {response_body}")
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
    print_command(f"meta_post: {node_url}")
    try:
        headers = {"codec-device": device}
        response = requests.post(
            f"{node_url}/~meta@1.0/info", 
            headers=headers, 
            data=json.dumps(config_content)
        )
        response_body = response.text
        print_info(f"Status: {response.status_code}")
        print_info(f"Body: {response_body}")
    except requests.RequestException as e:
        print_error(f"Error posting to meta: {e}") 