import asyncio
import os
import statistics
import threading
import time
from multiprocessing import Process
from typing import Union

import httpx


class TESTER:
    def __init__(
        self,
        api_requests: dict,
        test_duration: int = 600,
        virtual_user: int = 20,
        http_timeout: int = 60,
        port: int = 11434,
        method: str = "POST",
        url: str = "10.204.16.75",
        save_path: str = "./result",
    ):
        """
        Initialize the TESTER class for performing API stress tests.

        Args:
            api_requests (dict): Dictionary containing API request payloads.
            test_duration (int): Duration of the test in seconds. Default is 600.
            virtual_user (int): Number of virtual users to simulate. Default is 20.
            http_timeout (int): Timeout for HTTP requests in seconds. Default is 60.
            port (int): Port number to be used for the URL. Default is 11434.
            method (str): HTTP method to be used (e.g., 'POST'). Default is 'POST'.
            url (str): Base URL for the API requests.
            save_path (str): Directory path to save the results.
        """
        self.virtual_user = virtual_user
        self.http_timeout = http_timeout
        self.url = self._verify_url(url=url, port=port)
        self.test_duration = test_duration
        self.method = method
        self.api_requests = api_requests
        self.save_path = self._verify_save_path(save_path)

    def _verify_url(self, url: str, port: int) -> str:
        """
        Verify if the URL is reachable and return the formatted URL.

        Args:
            url (str): The base URL.
            port (int): The port number to be used.

        Returns:
            str: The formatted URL with the specified port.
        """
        test_ollama = f"http://{url}:{port}"
        try:
            response = httpx.get(test_ollama, timeout=10)
            if response.status_code == 200:
                print(f"URL {test_ollama} is reachable.")
            else:
                print(f"URL {test_ollama} returned status code {response.status_code}.")
        except httpx.RequestError as e:
            print(f"An error occurred: {e}")
        return f"http://{url}:{port}/api/chat"

    def _verify_save_path(self, path: str) -> str:
        """
        Verify if the save path exists, and create it if it does not.

        Args:
            path (str): The directory path to save the results.

        Returns:
            str: The verified save path.
        """
        if not os.path.isdir(path):
            os.makedirs(path)
        return path

    async def chat_stream(
        self, client: httpx.AsyncClient, request_data: dict
    ) -> Union[httpx.Response, None]:
        """
        Perform an asynchronous HTTP request to the chat API.

        Args:
            client (httpx.AsyncClient): The HTTP client to be used for the request.
            request_data (dict): The data to be sent in the request.

        Returns:
            Union[httpx.Response, None]: The response object if successful, otherwise None.
        """
        try:
            response = await client.request(
                self.method,
                self.url,
                json=request_data,
                timeout=self.http_timeout,
            )
            if response.status_code == 200:
                pass
            return response
        except httpx.RequestError as e:
            if isinstance(e, httpx.TimeoutException):
                pass
            else:
                pass
            return None

    async def process_response(self, task, metrics: dict) -> None:
        """
        Process the response from an asynchronous task and update the metrics.

        Args:
            task: The asyncio task to be processed.
            metrics (dict): Dictionary to store metrics such as successful requests, errors, etc.
        """
        try:
            result = await task
            if isinstance(result, httpx.Response) and result.status_code == 200:
                metrics["successful_requests"] += 1
                metrics["response_times"].append(result.elapsed.total_seconds())
            elif isinstance(result, httpx.Response):
                metrics["error_requests"] += 1
            elif result is None:
                metrics["canceled_requests"] += 1
            else:
                metrics["error_requests"] += 1
        except asyncio.CancelledError:
            metrics["canceled_requests"] += 1
        except Exception as e:
            print(f"Unexpected error occurred: {str(e)}")
            metrics["error_requests"] += 1

    async def make_requests(
        self, payload: list, duration: int, users: int, stop_event: threading.Event
    ) -> dict:
        """
        Make concurrent requests to the API for the given duration and track metrics.

        Args:
            payload (list): List of request payloads to be sent.
            duration (int): Duration for which the requests should be made.
            users (int): Number of concurrent users to simulate.
            stop_event (threading.Event): Event to signal stopping the requests.

        Returns:
            dict: Dictionary containing metrics for the requests.
        """
        start_time = time.time()
        end_time = start_time + duration
        metrics = {
            "successful_requests": 0,
            "error_requests": 0,
            "canceled_requests": 0,
            "response_times": [],
        }
        tasks = []

        async with httpx.AsyncClient() as client:
            while not stop_event.is_set() and time.time() < end_time:
                for p in payload:
                    if len(tasks) >= users:
                        # Wait for any of the tasks to complete if we've reached the user limit
                        done, pending = await asyncio.wait(
                            tasks, return_when=asyncio.FIRST_COMPLETED
                        )
                        tasks = list(pending)
                        for task in done:
                            asyncio.create_task(self.process_response(task, metrics))
                    # Submit new requests
                    tasks.append(asyncio.create_task(self.chat_stream(client, p)))
                await asyncio.sleep(0.1)

            # Cancel all pending tasks when the time is up
            for task in tasks:
                if not task.done():
                    task.cancel()
                    metrics["canceled_requests"] += 1

            # Wait for remaining tasks to complete
            done, _ = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
            for task in done:
                if not task.cancelled():
                    await self.process_response(task, metrics)

        total_requests = (
            metrics["successful_requests"]
            + metrics["error_requests"]
            + metrics["canceled_requests"]
        )

        requests_per_sec = (
            metrics["successful_requests"] / self.test_duration
            if metrics["response_times"]
            else 0
        )
        avg_response_time = (
            statistics.mean(metrics["response_times"])
            if metrics["response_times"]
            else 0
        )
        min_response_time = (
            min(metrics["response_times"]) if metrics["response_times"] else 0
        )
        max_response_time = (
            max(metrics["response_times"]) if metrics["response_times"] else 0
        )
        error_percentage = (
            (metrics["error_requests"] / total_requests * 100)
            if total_requests > 0
            else 0
        )

        return {
            "total_requests_sent": total_requests,
            "requests_per_second": requests_per_sec,
            "avg_response_time": avg_response_time,
            "min_response_time": min_response_time,
            "max_response_time": max_response_time,
            "error_percentage": error_percentage,
            "canceled_requests": metrics["canceled_requests"],
        }

    def run(self) -> None:
        """
        Run the API stress tests and collect metrics.
        """
        all_metrics = {}
        stop_event = threading.Event()

        async def run_tests():
            tasks = []
            for model, payload in self.api_requests.items():
                tasks.append(
                    self.make_requests(
                        payload, self.test_duration, self.virtual_user, stop_event
                    )
                )
            results = await asyncio.gather(*tasks)
            stop_event.set()

            for model, metrics in zip(self.api_requests.keys(), results):
                all_metrics[model] = metrics
                print(all_metrics[model])

            # Save results to file
            print("Saving result...")
            for model_name, metrics in all_metrics.items():
                with open(
                    os.path.join(
                        self.save_path,
                        f"api_metrics_{model_name.replace('/', '_').replace(':', '_')}.txt",
                    ),
                    "w",
                ) as f:
                    f.write(f"Model: {model_name}\n")
                    f.write(f"Total requests sent: {metrics['total_requests_sent']}\n")
                    f.write(f"Requests/s: {metrics['requests_per_second']:.2f}\n")
                    f.write(
                        f"Avg. response time (s): {metrics['avg_response_time']:.2f}\n"
                    )
                    f.write(f"Min(s): {metrics['min_response_time']:.2f}\n")
                    f.write(f"Max(s): {metrics['max_response_time']:.2f}\n")
                    f.write(f"Error %: {metrics['error_percentage']:.2f}%\n")
                    f.write(f"Canceled requests: {metrics['canceled_requests']}\n")
                    f.write("\n")

            print("End")

        asyncio.run(run_tests())


def run_tester(
    api_requests: dict,
    url: str,
    test_duration: int,
    http_timeout: int,
    virtual_user: int,
) -> None:
    """
    Run the tester with the provided parameters.

    Args:
        api_requests (dict): Dictionary containing API request payloads.
        url (str): The base URL for the API requests.
        test_duration (int): Duration of the test in seconds.
        http_timeout (int): Timeout for HTTP requests in seconds.
        virtual_user (int): Number of virtual users to simulate.
    """
    tester = TESTER(
        api_requests=api_requests,
        url=url,
        test_duration=test_duration,
        http_timeout=http_timeout,
        virtual_user=virtual_user,
    )
    tester.run()


if __name__ == "__main__":
    api_requests = {
        "llama3.1:latest": [
            {
                "model": "llama3.1:latest",
                "messages": [{"role": "user", "content": "how r u?"}],
                "stream": False,
            }
        ],
        "qwen2.5:1.5b": [
            {
                "model": "qwen2.5:1.5b",
                "messages": [{"role": "user", "content": "how r u?"}],
                "stream": False,
            }
        ],
        "llama3.2:1b": [
            {
                "model": "llama3.2:1b",
                "messages": [{"role": "user", "content": "how r u?"}],
                "stream": False,
            }
        ],
        "llama3.2-vision:latest": [
            {
                "model": "llama3.2-vision:latest",
                "messages": [{"role": "user", "content": "how r u?"}],
                "stream": False,
            }
        ],
        "llama3:latest": [
            {
                "model": "llama3:latest",
                "messages": [{"role": "user", "content": "how r u?"}],
                "stream": False,
            }
        ],
    }

    processes = []
    for model_name, request_payload in api_requests.items():
        p = Process(
            target=run_tester,
            args=(
                {model_name: request_payload},
                "172.17.0.3",
                600,
                60,
                20,
            ),
        )
        processes.append(p)
        p.start()

    for p in processes:
        p.join()
