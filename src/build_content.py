import os
import subprocess
import shutil

def build_guest_content(out_dir, dockerfile, hb_branch, ao_branch):

    docker_img="hb-content"

    # Prepare the output directory.
    print(f"Preparing output directory: {out_dir}")
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(os.path.join(out_dir, "hb"), exist_ok=True)

    # Build Docker image.
    print(f"Building Docker image: {docker_img}")
        # Ensure Dockerfile exists in the script_dir.
    if os.path.isfile(dockerfile):
        context_dir = os.path.dirname(dockerfile)
        dockerfile_arg = os.path.basename(dockerfile)

    # Save the current directory so we can return to it.
    old_dir = os.getcwd()
    os.chdir(context_dir)

    # Replace <HB_BRANCH> with the branch name.
    with open(dockerfile, "r") as f:
        dockerfile_content = f.read()
    dockerfile_content = dockerfile_content.replace("<HB_BRANCH>", hb_branch)
    dockerfile_content = dockerfile_content.replace("<AO_BRANCH>", ao_branch)
    with open(dockerfile, "w") as f:
        f.write(dockerfile_content)

    # Build the Docker image.
    try:
        # Note: In the command below the build context is ".", because we already cd'ed.
        if dockerfile_arg:
            build_cmd = f"docker build --build-arg CACHEBUST=$(date +%s) -t {docker_img} -f {dockerfile_arg} ."
        print("Running command:", build_cmd)
        subprocess.run(build_cmd, shell=True, check=True)
    finally:
        os.chdir(old_dir)

    # Revert the <HB_BRANCH> to the original value.
    with open(dockerfile, "r") as f:
        dockerfile_content = f.read()
    dockerfile_content = dockerfile_content.replace(hb_branch, "<HB_BRANCH>")
    dockerfile_content = dockerfile_content.replace(ao_branch, "<AO_BRANCH>")
    with open(dockerfile, "w") as f:
        f.write(dockerfile_content)

    # Run Docker container.
    print(f"Running Docker container: {docker_img}")
    subprocess.run(["docker", "stop", docker_img],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    subprocess.run(["docker", "run", "--rm", "-d", "--name", docker_img, docker_img, "sleep", "3600"],
                   check=True)

    # Copy files from the container.
    print(f"Copying /release from container to: {out_dir}")
    subprocess.run(["docker", "cp", f"{docker_img}:/release/.", out_dir], check=True)

    # Cleanup: Stop the container.
    print("Cleaning up...")
    subprocess.run(["docker", "stop", docker_img],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    print(f"Done! The /release folder has been copied to {out_dir}")
