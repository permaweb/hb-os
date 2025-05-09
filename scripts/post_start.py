#!/usr/bin/env python3
"""
Post-start script for VM initialization.
This script is executed after the VM has started and is ready.
It performs different actions based on the VM type (standalone, compute, or router).
"""

import sys
import os
import subprocess
import time
import requests
import json
import re
import argparse

# Ensure the script directory is in the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

# Define configuration directory path
CONFIG_DIR = os.path.join(script_dir, '..', 'config')

from node_api import (
    get_node_info, get_node_process_routes, register_node, meta_post,
    initialize_greenzone, join_node, become_node,
    print_error, print_success, print_warning, print_info, print_step, print_command, print_debug, Colors
)

def run_command(cmd):
    """
    Run a shell command and print its output.
    """
    print_command(f"{cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.stderr:
        print_error(f"Command error: {result.stderr}")
    return result.returncode == 0

def load_json_data(file_path):
    """
    Load JSON data from a file.
    """
    print_step(f"Loading JSON data from {file_path}")
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        return data
    except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
        print_error(f"Error loading JSON data from {file_path}: {e}")
        return None

def load_jsonc_file(file_path):
    """
    Load a JSONC file (JSON with comments) by removing comments before parsing.
    
    Args:
        file_path: Path to the JSONC file
        
    Returns:
        Parsed JSON data as dict or None if there was an error
    """
    # Get just the filename for cleaner output
    filename = os.path.basename(file_path)
    print_step(f"Loading JSONC file from {filename}")
    try:
        with open(file_path, 'r') as file:
            content = file.read()
            
        # Remove single-line comments (// ...)
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        
        # Remove multi-line comments (/* ... */)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Parse the JSON content
        return json.loads(content)
    except FileNotFoundError:
        print_error(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        print_error(f"Error parsing JSON in {file_path}: {e}")
        print_info(f"First 100 chars of processed content: {content[:100] if content else 'Empty file'}")
        return None
    except Exception as e:
        print_error(f"Unexpected error loading {file_path}: {e}")
        return None

def get_ip_address(json_data):
    """
    Get IP address using multiple methods.
    
    Args:
        json_data: JSON data containing VM configuration which may include IP address
        
    Returns:
        str: IP address or "localhost" if no IP could be determined
    """
    ip_address = None

    # Method 1: Try to use hostname command
    try:
        result = subprocess.run("hostname -I | awk '{print $1}'", shell=True, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            ip_address = result.stdout.strip()
            print_info(f"Using IP address from hostname command: {ip_address}")
            return ip_address
    except Exception as e:
        print_warning(f"Error getting IP address using hostname: {e}")
    
    # Method 2: Try using ip command
    try:
        result = subprocess.run("ip -4 addr show | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}' | grep -v 127.0.0.1 | head -n 1", 
                                shell=True, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            ip_address = result.stdout.strip()
            print_info(f"Using IP address from ip command: {ip_address}")
            return ip_address
    except Exception as e:
        print_warning(f"Error getting IP address using ip command: {e}")
    
    # Default to localhost if all methods fail
    print_warning("Could not determine IP address. Using default: localhost")
    return "localhost"

def prepare_snp_trusted_data(json_data):
    """
    Prepare SNP trusted data from json_data, excluding expected_hash.
    
    Args:
        json_data: JSON data containing SNP hashes
        
    Returns:
        dict: Filtered copy of json_data with expected_hash removed
    """
    if not json_data or not isinstance(json_data, dict):
        return {}
        
    # Create a filtered copy of json_data without expected_hash
    snp_data = json_data.copy()
    if 'expected_hash' in snp_data:
        del snp_data['expected_hash']
        print_info("Excluded expected_hash from SNP trusted data")
        
    return snp_data

def replace_placeholders(config, node_info=None, peer_info=None):
    """
    Replace placeholder variables in configuration with actual values.
    
    Args:
        config: Configuration dictionary to modify
        node_info: Information about the current node
        peer_info: Information about the peer node
        
    Returns:
        dict: Updated configuration with placeholders replaced
    """
    print_step(f"Replacing placeholder variables in configuration")
    # Skip if either config is not a dict or missing node_info
    if not isinstance(config, dict) or not node_info:
        return config
        
    # Define replacement mappings
    replacements = {}
    if node_info:
        replacements["$SELF"] = node_info.get('location', '')
        replacements["$SELF_ID"] = node_info.get('id', '')
    
    # Add router replacements if available
    if peer_info:
        replacements["$PEER"] = peer_info.get('location', '')
        replacements["$PEER_ID"] = peer_info.get('id', '')
    
    # Print available replacements for debugging
    print_info("Available placeholder replacements:")
    for key, value in replacements.items():
        print_info(f"{Colors.RED}{key}{Colors.RESET} -> {Colors.YELLOW}{value}{Colors.RESET}")
    
    # Track which replacements were actually used
    used_replacements = set()
    
    # Recursively process the config dictionary
    def process_dict(d):
        if not isinstance(d, dict):
            return d
            
        result = {}
        for key, value in d.items():
            # If value is a string, check for replacements
            if isinstance(value, str) and value in replacements:
                result[key] = replacements[value]
                used_replacements.add(value)
                print_info(f"Replaced placeholder {value} with {replacements[value]} in field '{key}'")
            # If value is a dict, process it recursively
            elif isinstance(value, dict):
                result[key] = process_dict(value)
            # If value is a list, process each item
            elif isinstance(value, list):
                result[key] = [process_dict(item) if isinstance(item, dict) else item for item in value]
            # Otherwise keep as is
            else:
                result[key] = value
        return result
    
    processed_config = process_dict(config)
    
    # Print summary of replacements
    if used_replacements:
        print_success(f"Applied {len(used_replacements)} placeholder replacements: {', '.join(used_replacements)}")
    else:
        print_debug("No placeholders were found in the configuration")
    
    return processed_config

def load_and_update_config(config_path, json_data, node_info=None, peer_info=None):
    """
    Load configuration from file, update with SNP trusted data and node information.
    
    Args:
        config_path: Path to configuration file
        json_data: JSON data with SNP hash information
        node_info: Information about the current node
        peer_info: Information about the peer node
        
    Returns:
        dict: Updated configuration or None if loading failed
    """
    # Load the configuration file
    config = load_jsonc_file(config_path)
    if not config:
        print_error(f"Failed to load configuration from {config_path}")
        print_error("Configuration file is required. Exiting.")
        return None
    
    print_success(f"Loaded configuration from {config_path}")
    
    # Update SNP trusted data
    snp_data = prepare_snp_trusted_data(json_data)
    if snp_data:
        config['snp_trusted'] = [snp_data]
        print_success(f"Updated SNP trusted hashes in configuration")
    
    # Replace placeholder variables in the configuration
    if node_info:
        config = replace_placeholders(config, node_info, peer_info)
        print_success(f"Replaced placeholder variables in configuration")
    
    # Print the updated config for debugging
    print_debug(f"Final configuration: {json.dumps(config, indent=4)}")
    return config
        
def format_url(url):
    """
    Format a URL if it doesn't already start with http:// or https://
    """
    if not url.startswith(('http://', 'https://')):
        return f"http://{url}"
    return url

def main():
    """
    Main entry point for post-start script.
    """
    print_step(f"Post-start script running")
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Post-start script for VM initialization')
    parser.add_argument('--inputs', required=True, help='Path to the JSON file containing VM configuration')
    parser.add_argument('--self', required=True, help='URL of the current VM')
    parser.add_argument('--peer', help='URL of the peer VM (if any)')
    
    # Default values
    node_info = None
    peer_info = None
    json_data = None
    
    # Parse arguments
    args = parser.parse_args()
    
    # Load JSON data from file
    if args.inputs:
        json_data = load_json_data(args.inputs)

    # Get node information for self
    if args.self:
        node_url = args.self
        node_url = format_url(node_url)
        node_info = get_node_info(node_url)
        
    # Get peer information if provided
    if args.peer:
        peer_url = args.peer
        peer_url = format_url(peer_url)
        peer_info = get_node_info(peer_url)

    # Load Server Config
    config_path = os.path.join(CONFIG_DIR, 'server.jsonc')
    config = load_and_update_config(
        config_path=config_path, 
        json_data=json_data, 
        node_info=node_info,
        peer_info=peer_info,
    )

    # If config is loaded successfully send requests to node
    if config:
        is_greenzone_host = False
        # Check if greenzone required config exists and set is_greenzone_host to True if so
        # If greenzone required config is empty, remove it from configuration
        if config and 'green_zone_required_config' in config:
            if config['green_zone_required_config'] == {}:
                print_warning("Greenzone required config is empty, removing it from configuration")
                print_info(f"Its removed so the node will use the default greenzone required config")
                del config['green_zone_required_config']
            is_greenzone_host = True

        # Post updated configuration to compute node
        meta_post(node_info['location'], config, 'json@1.0')
        # Register compute node with peer if router_peer_location is configured
        if config and 'router_peer_location' in config:
            print_info(f"Router peer location found in config, registering node")
            register_node(node_info['location'])
        else:
            print_debug(f"No router_peer_location in config, skipping node registration")
        
        # Join and become a node in a Greenzone if green_zone_peer_location is configured
        if config and 'green_zone_peer_location' in config:
            print_info(f"Greenzone peer location found in config, joining greenzone")
            join_node(node_info['location'], config['green_zone_peer_location'], config['green_zone_peer_id'], config['green_zone_adopt_config'])
            become_node(node_info['location'], config['green_zone_peer_location'], config['green_zone_peer_id'])
        else:
            print_debug(f"No green_zone_peer_location in config, skipping connection to greenzone")
        
        # Initialize Greenzone if green_zone_required_config is configured
        if is_greenzone_host == True:
            print_info(f"Greenzone required config found in config, initializing greenzone")
            initialize_greenzone(node_info['location'])
        else:
            print_debug(f"No green_zone_required_config in config, skipping greenzone initialization")
        
    print_success("Post-start script completed successfully")

if __name__ == "__main__":
    main()
