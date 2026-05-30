import { apiError } from "@/lib/api-response";

export async function POST() {
  return apiError("bad_request", "请通过具体业务接口上传文件", 400);
}
