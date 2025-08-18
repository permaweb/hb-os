import os
import time
from typing import Optional
from src.utils import remove_directory, ensure_directory
from src.services import docker_service, DockerfileTemplateProcessor

def build_guest_content(out_dir: str, dockerfile: str, hb_branch: str, ao_branch: str, debug: bool = False) -> None:
    """
    Build guest content using Docker with proper resource management.
    
    Args:
        out_dir (str): Output directory for the built content
        dockerfile (str): Path to the Dockerfile template
        hb_branch (str): HyperBEAM branch to use
        ao_branch (str): AO branch to use
        debug (bool): Skip HyperBEAM building steps if True
        
    Raises:
        DockerError: If any Docker operation fails
        FileSystemError: If required files are missing
    """
    docker_img = "hb-content"
    container_name = "hb-content"

    # Prepare the output directory.
    print(f"Preparing output directory: {out_dir}")
    remove_directory(out_dir)
    ensure_directory(os.path.join(out_dir, "hb"))

    context_dir = os.path.dirname(dockerfile)
    dockerfile_name = os.path.basename(dockerfile)

    # Process Dockerfile template with automatic restoration
    template_vars = {
        "HB_BRANCH": hb_branch,
        "AO_BRANCH": ao_branch
    }
    
    with DockerfileTemplateProcessor.managed_template(dockerfile, template_vars):
        # Build Docker image with cache busting and debug flag
        build_args = {
            "CACHEBUST": str(int(time.time())),
            "SKIP_HYPERBEAM": "true" if debug else "false"
        }
        
        if debug:
            print("🐛 Debug mode: Building Docker image with SKIP_HYPERBEAM=true")
        else:
            print("📦 Production mode: Building Docker image with SKIP_HYPERBEAM=false")
        
        docker_service.build_image(context_dir, dockerfile_name, docker_img, build_args)

        # Run container and copy files with automatic cleanup
        with docker_service.managed_container(docker_img, container_name) as container:
            # Copy files from the container
            docker_service.copy_from_container(container, "/release/.", out_dir)

    print(f"✅ Done! The /release folder has been copied to {out_dir}")
