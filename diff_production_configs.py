"""
Script to compare configs from SANDAG/ABM release with configs from ActivitySim/sandag-abm3-example repo
"""

import os
import sys
import shutil
import tempfile
import subprocess
import zipfile
import requests
import argparse
from pathlib import Path


def get_latest_release(repo_owner, repo_name):
    """Fetch the latest release tag from GitHub API"""
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()['tag_name']
    except Exception as e:
        print(f"Error fetching latest release: {e}")
        return None


def run_command(cmd, cwd=None):
    """Run a shell command and return the output"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        print(f"Error: {e.stderr}")
        sys.exit(1)


def download_release(url, dest_dir):
    """Download the release from GitHub"""
    print(f"Downloading release from {url}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    zip_path = dest_dir / "release.zip"
    with open(zip_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"Downloaded to {zip_path}")
    return zip_path


def extract_configs(zip_path, extract_dir):
    """Extract src/asim/configs folder from the release"""
    print("Extracting configs folder...")
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # List all files to find the correct path structure
        all_files = zip_ref.namelist()
        
        # Find files matching the pattern
        config_files = [f for f in all_files if 'src/asim/configs' in f]
        
        if not config_files:
            print("Warning: Could not find src/asim/configs in archive")
            print("Looking for alternative paths...")
            config_files = [f for f in all_files if 'configs' in f or 'configs/' in f]
        
        if not config_files:
            print("Available paths in archive:")
            for f in all_files[:20]:  # Show first 20 files
                print(f"  {f}")
            raise ValueError("Could not find configs folder in the archive")
        
        # Extract matching files
        for file in config_files:
            zip_ref.extract(file, extract_dir)
    
    # Find the extracted configs directory
    configs_path = None
    for root, dirs, files in os.walk(extract_dir):
        if root.endswith('configs') or (os.path.basename(root) == 'configs'):
            configs_path = Path(root)
            break
    
    if not configs_path:
        raise ValueError("Could not locate extracted configs folder")
    
    print(f"Extracted configs to {configs_path}")
    return configs_path


def clone_comparison_repo(repo_url, dest_dir, branch=None):
    """Clone the comparison repository"""
    clone_cmd = f"git clone {repo_url} comparison_repo"
    if branch:
        clone_cmd += f" --branch {branch}"
    
    print(f"Cloning comparison repo {repo_url}" + (f" (branch: {branch})" if branch else " (default branch)") + "...")
    run_command(clone_cmd, cwd=dest_dir)
    return dest_dir / "comparison_repo"


def perform_diff(source_dir, target_repo_dir, summary_only=True, subdir=None):
    """Perform git diff between the two directories"""
    print("\n" + "="*80)
    print("PERFORMING DIFF")
    print("="*80 + "\n")
    
    # Copy source configs to target repo for comparison
    # Find a suitable subdirectory in target repo to compare against
    target_configs = target_repo_dir / "configs"
    
    if not target_configs.exists():
        print(f"Warning: {target_configs} does not exist in comparison repo")
        print("Available directories:")
        for item in target_repo_dir.iterdir():
            if item.is_dir():
                print(f"  {item.name}")
        return
    
    # If subdirectory specified, navigate to it
    if subdir:
        source_dir = source_dir / subdir
        target_configs = target_configs / subdir
        
        if not source_dir.exists():
            print(f"Error: Subdirectory '{subdir}' not found in source configs at {source_dir}")
            print(f"Available subdirectories in source:")
            parent = source_dir.parent
            for item in parent.iterdir():
                if item.is_dir():
                    print(f"  {item.name}")
            return
        
        if not target_configs.exists():
            print(f"Error: Subdirectory '{subdir}' not found in target configs at {target_configs}")
            print(f"Available subdirectories in target:")
            parent = target_configs.parent
            for item in parent.iterdir():
                if item.is_dir():
                    print(f"  {item.name}")
            return
    
    # Use git diff to compare
    print(f"Comparing:")
    print(f"  Source: {source_dir}")
    print(f"  Target: {target_configs}")
    print("\n" + "-"*80 + "\n")
    
    # Perform diff using git directly on both directories
    try:
        if summary_only:
            # Show only file names and status
            result = subprocess.run(
                ['git', 'diff', '--no-index', '--name-status', str(target_configs), str(source_dir)],
                cwd=target_repo_dir,
                capture_output=True,
                text=True
            )
        else:
            # Show full diff
            result = subprocess.run(
                ['git', 'diff', '--no-index', str(target_configs), str(source_dir)],
                cwd=target_repo_dir,
                capture_output=True,
                text=True
            )
        
        # git diff returns exit code 1 when differences exist, which is expected
        if result.stdout:
            if summary_only:
                print("Files with differences (M=Modified, A=Added, D=Deleted):\n")
            print(result.stdout)
        elif result.returncode == 0:
            print("No differences found between the configurations!")
        else:
            print(f"Error performing diff: {result.stderr}")
    except Exception as e:
        print(f"Error running git diff: {e}")


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Compare SANDAG/ABM release configs with ActivitySim example repo',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Examples:
            %(prog)s                                   # Use latest release, default branch, summary mode, all configs
            %(prog)s -r v15.3.1                        # Use specific release, summary mode, all configs
            %(prog)s -r v15.3.1 -f                     # Use specific release, full diff output
            %(prog)s -r v15.3.1 -d resident            # Diff only the resident subdirectory
            %(prog)s -d commercial --full              # Diff commercial subdirectory with full output
            %(prog)s -r v15.3.1 -b develop -d resident # Specific release, branch, and subdirectory
        """
    )
    parser.add_argument(
        '-r', '--release',
        type=str,
        default=None,
        help='Release tag/version to compare (e.g., v15.3.1). If not specified, uses the latest release.'
    )
    parser.add_argument(
        '-b', '--branch',
        type=str,
        default=None,
        help='Branch of the comparison repo to diff against (e.g., main, develop). If not specified, uses the default branch.'
    )
    parser.add_argument(
        '-f', '--full',
        action='store_true',
        help='Show full diff output instead of just file names (summary mode is default).'
    )
    parser.add_argument(
        '-d', '--subdir',
        type=str,
        default=None,
        help='Subdirectory within configs to diff (e.g., resident, commercial). If not specified, diffs entire configs directory.'
    )
    
    args = parser.parse_args()
    
    # Configuration
    REPO_OWNER = "SANDAG"
    REPO_NAME = "ABM"
    COMPARISON_REPO = "https://github.com/ActivitySim/sandag-abm3-example.git"
    
    # Determine which release to use
    if args.release:
        release_tag = args.release
        print(f"Using specified release: {release_tag}")
    else:
        print("Fetching latest release...")
        release_tag = get_latest_release(REPO_OWNER, REPO_NAME)
        if not release_tag:
            print("Error: Could not fetch latest release. Please specify a release with -r")
            sys.exit(1)
        print(f"Using latest release: {release_tag}")
    
    # Construct release URL
    RELEASE_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/tags/{release_tag}.zip"
    
    # Create temporary working directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        print(f"Working directory: {temp_path}\n")
        
        try:
            # Step 1: Download release
            zip_path = download_release(RELEASE_URL, temp_path)
            
            # Step 2: Extract configs
            configs_dir = extract_configs(zip_path, temp_path)
            
            # Step 3: Clone comparison repo
            comparison_repo = clone_comparison_repo(COMPARISON_REPO, temp_path, args.branch)
            
            # Step 4: Perform diff
            perform_diff(configs_dir, comparison_repo, summary_only=not args.full, subdir=args.subdir)
            
            print("\n" + "="*80)
            print("DIFF COMPLETE")
            print("="*80)
            
        except Exception as e:
            print(f"\nError: {e}")
            sys.exit(1)


if __name__ == "__main__":
    # Check for required tools
    required_tools = ['git']
    for tool in required_tools:
        if shutil.which(tool) is None:
            print(f"Error: {tool} is not installed or not in PATH")
            sys.exit(1)
    
    main()