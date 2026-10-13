"""AI enhancement ("Migliora") of samples, on this computer only.

Every job runs in a child process (see runner.py) that loads just the chosen model and exits when done: PyTorch
is never imported by the app itself, and all of the model's memory goes back to the system after each job.
"""
