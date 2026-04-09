"""Demo module for GL-IAM API Key Hierarchy Example.

This module contains demonstration scripts that showcase different
aspects of the API key hierarchy feature.

Each demo module is independent and can be run individually.
This follows the Liskov Substitution Principle - all demos
can be substituted interchangeably in the main orchestrator.
"""

from .bootstrap_demo import run_bootstrap_demo
from .organization_demo import run_organization_demo
from .child_keys_demo import run_child_keys_demo
from .validation_demo import run_validation_demo
from .hierarchy_demo import run_hierarchy_demo

__all__ = [
    "run_bootstrap_demo",
    "run_organization_demo",
    "run_child_keys_demo",
    "run_validation_demo",
    "run_hierarchy_demo",
]
