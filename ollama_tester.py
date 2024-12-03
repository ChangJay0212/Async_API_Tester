import asyncio
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
        self.url = self._verify_url(url=url, port=port)
        self.test_duration = test_duration
        self.method = method
        self.api_requests = api_requests
        self.save_path = self._verify_save_path(save_path)

    def _verify_url(self, url: str, port: int):
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

    async def chat_stream(self, client: httpx.AsyncClient, request_data: dict):
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

    async def process_response(self, task, metrics):
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

    async def make_requests(self, payload, duration, users, stop_event):
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

    def run(self):
        all_metrics = {}
        stop_event = threading.Event()

        # def countdown_timer():
        #     start_time = time.time()
        #     while not stop_event.is_set():
        #         elapsed_time = time.time() - start_time
        #         remaining_time = self.test_duration - elapsed_time
        #         if remaining_time < 0:
        #             break
        #         print(
        #             f"Elapsed Time: {elapsed_time:.2f}s / {self.test_duration}s, Remaining Time: {remaining_time:.2f}s",
        #             end="\r",
        #             file=sys.stdout,
        #         )
        #         time.sleep(1)

        # timer_thread = threading.Thread(target=countdown_timer)
        # timer_thread.start()

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
            # timer_thread.join()

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
                        f"Avg. response time (ms): {metrics['avg_response_time']:.2f}\n"
                    )
                    f.write(f"Min(ms): {metrics['min_response_time']:.2f}\n")
                    f.write(f"Max(ms): {metrics['max_response_time']:.2f}\n")
                    f.write(f"Error %: {metrics['error_percentage']:.2f}%\n")
                    f.write(f"Canceled requests: {metrics['canceled_requests']}\n")
                    f.write("\n")

            print("End")

        asyncio.run(run_tests())


def run_tester(api_requests, url, test_duration, http_timeout, virtual_user):
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
        # "llama3.2-vision:latest": [
        #     {
        #         "model": "llama3.2-vision:latest",
        #         "messages": [{"role": "user", "content": "how r u?"}],
        #         "stream": False,
        #     }
        # ],
        "llama3:latest": [
            {
                "model": "llama3:latest",
                "messages": [{"role": "user", "content": "how r u?"}],
                "stream": False,
            }
        ],
    }
    from multiprocessing import Process

    # 使用多进程分别启动每个 API 的测试
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

    # 等待所有进程完成
    for p in processes:
        p.join()
