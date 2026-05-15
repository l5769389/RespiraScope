import asyncio
import time

# 阻塞式（错误做法）
async def blocking_example():
    print("开始阻塞任务")
    time.sleep(3)  # 这会阻塞整个事件循环
    print("阻塞任务完成")

# 非阻塞式（正确做法）
async def non_blocking_example():
    start =time.time()
    print("开始后台任务")
    loop = asyncio.get_event_loop()
    # 在线程池中执行，不阻塞事件循环
    await loop.run_in_executor(None, time.sleep, 3)
    print("后台任务完成", time.time() - start)

async def other_task():
    for i in range(5):
        print(f"其他任务运行中: {i}")
        await asyncio.sleep(1)

# 测试
async def main():
    # 并发执行两个任务
    await asyncio.gather(
        non_blocking_example(),
        other_task()
    )

if __name__ == "__main__":
    asyncio.run(main())
