# utils/logger_config.py
import logging
import sys
import os

def setup_logger(logger_name, level=logging.INFO, log_file=None, console_output=True):
    logger = logging.getLogger(logger_name)
    
    if logger.hasHandlers():
        return logger

    logger.setLevel(level)
    logger.propagate = False 

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s (%(filename)s:%(lineno)d)'
    )

    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file:
        try:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not set up file logger for {log_file}: {e}")
            if not logger.hasHandlers():
                emergency_handler = logging.StreamHandler(sys.stderr)
                emergency_handler.setFormatter(formatter)
                logger.addHandler(emergency_handler)
                logger.warning(f"File logger for {log_file} failed. Logging to stderr as fallback.")
    return logger