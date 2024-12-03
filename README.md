# Ollama High-Load Performance Tester

## Overview
The **Ollama High-Load Performance Tester** is a tool specifically designed to benchmark Ollama's API under high load conditions. It measures key performance metrics such as response time, request rate, and error percentage, providing insights into Ollama's API performance when handling multiple concurrent requests. This tool is particularly useful for stress testing and validating the robustness of Ollama's deployment.

## Features
- Supports concurrent requests to multiple API endpoints.
- Collects detailed performance metrics, including:
  - Total requests sent
  - Requests per second
  - Average response time
  - Minimum and maximum response times
  - Error rate
  - Canceled requests
- Uses multithreading to handle countdown and track test duration.
- Uses asyncio for concurrent API requests, ensuring efficient high-load testing.

## Requirements
To use this tool, you need Python 3.8 or above and the following packages installed:

- `httpx`: HTTP client for making API requests.
  
  Install via pip:
  ```sh
  pip install httpx
  ```

All other required libraries (`asyncio`, `statistics`, `threading`, `time`, `os`, `sys`) are part of the Python standard library.

## Usage
1. **Setup**: Clone the repository or copy the script to your local machine.
2. **Configuration**: Modify the `api_requests` dictionary in the script to include the models and APIs you wish to test.
   
   Example:
   ```python
   api_requests = {
       "llama3:latest": [
           {
               "model": "llama3:latest",
               "messages": [{"role": "user", "content": "how r u?"}],
               "stream": False,
           }
       ],
       "llama3.1:latest": [
           {
               "model": "llama3.1:latest",
               "messages": [{"role": "user", "content": "how r u?"}],
               "stream": False,
           }
       ],
   }
   ```
3. **Run the Script**: Execute the script using Python:
   ```sh
   python ollama_performance_tester.py
   ```
4. **Results**: Metrics are saved in text files named after the API models tested, e.g., `api_metrics_llama3_latest.txt`.

## Metrics
The following metrics are collected for each API model:
- **Total Requests Sent**: The total number of API requests made during the test.
- **Requests per Second**: The number of successful requests per second.
- **Average Response Time**: The average response time in milliseconds.
- **Min/Max Response Time**: The shortest and longest response times in milliseconds.
- **Error Percentage**: The percentage of requests that resulted in errors.
- **Canceled Requests**: The number of requests that were canceled, for example, due to the test duration ending.

## Customization
- **Duration and Number of Users**: You can adjust the duration (`test_duration`) and the number of concurrent users (`virtual_user`) in the `TESTER` class to simulate different loads.
- **Timeout Settings**: Adjust the `http_timeout` value in the `TESTER` class to control how long each API request will wait for a response.
- **Target URL and Port**: Modify the `url` and `port` parameters in the `TESTER` class to point to your specific Ollama API endpoint.

## Example Output
The output metrics for each model are saved in separate `.txt` files. Example content:

```
Model: llama3:latest
Total requests sent: 500
Requests/s: 20.15
Avg. response time (ms): 150.45
Min(ms): 100.30
Max(ms): 350.60
Error %: 2.00%
Canceled requests: 10
```

## License
This project is licensed under the MIT License.

