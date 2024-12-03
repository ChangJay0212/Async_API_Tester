import concurrent.futures
import os
import statistics
import threading
import time

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
        self.virtual_user = virtual_user
        self.http_timeout = http_timeout
        self.url = self._veridt_url(url=url, port=port)
        self.test_duration = test_duration
        self.method = method
        self.api_requests = api_requests
        self.save_path = self._verify_save_path(save_path)

    def _veridt_url(self, url: str, port: int):
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

    def _verify_save_path(self, path: str):
        if not os.path.isdir(path):
            os.makedirs(path)
        return path

    def chat_stream(self, request_data: dict) -> str:
        try:
            with httpx.stream(
                self.method,
                self.url,
                json=request_data,
                timeout=self.http_timeout,
            ) as response:
                response.encoding = "utf-8"
                return response
        except BaseException as e:
            return f"Error occurred: {str(e)}\n\n"

    def _handle_results(self, futures, results, metrics, stop_event):
        while not stop_event.is_set() or futures:
            completed_futures = []
            try:
                completed_futures = [
                    f for f in concurrent.futures.as_completed(futures, timeout=1)
                ]
            except concurrent.futures.TimeoutError:
                pass

            for future in completed_futures:
                try:
                    result = future.result()
                    results.append(result)
                    if isinstance(result, httpx.Response) and result.status_code == 200:
                        metrics["successful_requests"] += 1
                        metrics["response_times"].append(
                            result.elapsed.total_seconds() * 1000
                        )
                    else:
                        metrics["error_requests"] += 1
                except Exception:
                    results.append((None, None))
                    metrics["error_requests"] += 1
                futures.remove(future)

            if stop_event.is_set():
                futures.clear()

    def make_requests(self, payload=None, duration=600, users=10, stop_event=None):
        end_time = time.time() + duration
        results = []
        metrics = {"successful_requests": 0, "error_requests": 0, "response_times": []}
        futures = set()

        with concurrent.futures.ThreadPoolExecutor(max_workers=users) as executor:
            result_thread = threading.Thread(
                target=self._handle_results,
                args=(futures, results, metrics, stop_event),
            )
            result_thread.start()

            try:
                while not stop_event.is_set() and time.time() < end_time:
                    new_futures = [
                        executor.submit(self.chat_stream, p) for p in payload
                    ]

                    if result_thread.is_alive():
                        futures.update(new_futures)
                    else:
                        break
                    time.sleep(0.1)
            finally:
                stop_event.set()
                result_thread.join()

        total_requests = metrics["successful_requests"] + metrics["error_requests"]
        requests_per_sec = (
            total_requests / (sum(metrics["response_times"]) / 1000)
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
        }

    def run(self):
        all_metrics = {}
        stop_event = threading.Event()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(
                    self.make_requests,
                    payload,
                    self.test_duration,
                    self.virtual_user,
                    stop_event,
                ): model
                for model, payload in self.api_requests.items()
            }
            try:
                start_time = time.time()
                while time.time() - start_time < self.test_duration:
                    time.sleep(1)
                    print(
                        f"Start evaluate : {int(time.time() - start_time)}/{self.test_duration} (s) "
                    )
            except KeyboardInterrupt:
                stop_event.set()

            stop_event.set()
            print("Start calculate Metrics! ")

            for future in futures:
                try:
                    model_name = futures[future]
                    print(model_name)
                    metrics = future.result()

                    all_metrics[model_name] = metrics
                    print(all_metrics[model_name])
                except Exception as e:
                    print(f"Error occurred for model {model_name}: {str(e)}")

        print("Saving result... ")
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
                    f"Avg. response time (ms): {metrics['avg_response_time']:.2f}\n"
                )
                f.write(f"Min(ms): {metrics['min_response_time']:.2f}\n")
                f.write(f"Max(ms): {metrics['max_response_time']:.2f}\n")
                f.write(f"Error %: {metrics['error_percentage']:.2f}%\n")
                f.write("\n")

        print("End ")


if __name__ == "__main__":
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

    tester = TESTER(
        api_requests=api_requests,
        url="10.204.16.75",
        test_duration=2,
        http_timeout=3,
        virtual_user=1,
    )
    tester.run()
