import base64
import os
import sys
import time
from pathlib import Path

from tencentcloud.common import credential
from tencentcloud.scf.v20180416 import models, scf_client

# 已有云函数的资源名称与 GitHub 仓库名称可以不同。
FUNCTION_NAME = "siss"
NAMESPACE = "default"
REGION = "ap-nanjing"


def main():
    secret_id = os.environ.get("TENCENT_SECRET_ID")
    secret_key = os.environ.get("TENCENT_SECRET_KEY")
    if not secret_id or not secret_key:
        raise RuntimeError("缺少腾讯云密钥，请检查 GitHub Actions secrets")
    if len(sys.argv) != 2:
        raise RuntimeError("用法：python scf/deploy.py scf.zip")
    package = Path(sys.argv[1]).read_bytes()
    if len(package) > 20 * 1024 * 1024:
        raise RuntimeError("代码包超过 SCF 接口 20 MB 限制")

    client = scf_client.ScfClient(credential.Credential(secret_id, secret_key), REGION)
    query = models.GetFunctionRequest()
    query.FunctionName = FUNCTION_NAME
    query.Namespace = NAMESPACE
    before = client.GetFunction(query)
    if before.Status != "Active":
        raise RuntimeError(f"函数状态不是 Active：{before.Status} {before.StatusDesc}")
    print(f"准备更新 {REGION}/{NAMESPACE}/{FUNCTION_NAME}", flush=True)

    request = models.UpdateFunctionCodeRequest()
    request.FunctionName = FUNCTION_NAME
    request.Namespace = NAMESPACE
    request.ZipFile = base64.b64encode(package).decode("ascii")
    request.Publish = "FALSE"
    response = client.UpdateFunctionCode(request)
    print(f"更新请求已提交，RequestId: {response.RequestId}", flush=True)

    # 给状态变化留出时间，然后等待函数恢复正常。
    time.sleep(10)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        result = client.GetFunction(query)
        print(f"函数状态：{result.Status} {result.StatusDesc or ''}", flush=True)
        if result.Status == "Active":
            if (result.CodeResult or "").lower() == "failed":
                raise RuntimeError(f"代码更新失败：{result.CodeError}")
            print("云函数代码更新完成", flush=True)
            return
        if result.Status in ("CreateFailed", "UpdateFailed", "DeleteFailed"):
            raise RuntimeError(f"函数更新失败：{result.StatusDesc}")
        time.sleep(5)
    raise TimeoutError("等待云函数更新超时")


if __name__ == "__main__":
    main()
