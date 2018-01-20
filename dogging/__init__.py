from .dog import *

# Get version
from pkg_resources import get_distribution, DistributionNotFound
try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    __version__ = None
finally:
    del get_distribution, DistributionNotFound
