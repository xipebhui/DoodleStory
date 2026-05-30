import { prisma } from "@/lib/prisma";

type QueueJob =
  | {
      type: "generation-task";
      taskId: string;
    }
  | {
      type: "style-test";
      styleTestId: string;
    };

class InMemoryQueue {
  private jobs: QueueJob[] = [];
  private running = false;

  enqueue(job: QueueJob) {
    this.jobs.push(job);
    void this.drain();
  }

  size() {
    return this.jobs.length;
  }

  private async drain() {
    if (this.running) {
      return;
    }

    this.running = true;

    try {
      while (this.jobs.length > 0) {
        const job = this.jobs.shift();

        if (!job) {
          continue;
        }

        if (job.type === "generation-task") {
          await prisma.generationTask.update({
            where: { id: job.taskId },
            data: {
              status: "failed",
              errorCode: "provider_not_configured",
              errorMessage: "图片生成 Provider 尚未接入，任务未进入生图流程。",
              finishedAt: new Date(),
            },
          });
        }

        if (job.type === "style-test") {
          await prisma.styleTest.update({
            where: { id: job.styleTestId },
            data: {
              status: "failed",
              errorCode: "provider_not_configured",
              errorMessage: "图片生成 Provider 尚未接入，测试未进入生图流程。",
              finishedAt: new Date(),
            },
          });
        }
      }
    } finally {
      this.running = false;
    }
  }
}

const globalForQueue = globalThis as unknown as {
  doodleStoryQueue?: InMemoryQueue;
};

export const taskQueue = globalForQueue.doodleStoryQueue ?? new InMemoryQueue();

if (process.env.NODE_ENV !== "production") {
  globalForQueue.doodleStoryQueue = taskQueue;
}
