# scripts

This folder contains various scripts used for running selected variations of
the SANDAG ABM3 example model.  Scripts that run on "small" or "test-scale" data
use the data files included in this repository, which only include a small subset
of the full data.  Scripts that run on "full-scale" data will download the full
data files (which are quite large) from GitHub if they are not available.

- `run-small-sharrow.py`: This script runs the test-scale version of this model,
    with sharrow enabled. If this is the first time you are running this script
    it may take a while to compile the code for the various component models.