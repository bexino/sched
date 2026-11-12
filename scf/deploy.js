// 只更新现有函数的代码，保留运行环境、触发器和其他配置。
const fs = require('fs')
const { Client } = require('tencentcloud-sdk-nodejs-scf').scf.v20180416

async function main() {
  const { TENCENT_SECRET_ID: secretId, TENCENT_SECRET_KEY: secretKey } = process.env
  if (!secretId || !secretKey) throw new Error('缺少腾讯云密钥，请检查 GitHub Actions Secrets')
  if (!process.argv[2]) throw new Error('请提供函数 ZIP 文件路径')

  const zip = fs.readFileSync(process.argv[2])
  if (zip.length > 20 * 1024 * 1024) throw new Error('函数代码包超过 API 的 20 MB 限制')
  const client = new Client({
    credential: { secretId, secretKey },
    region: 'ap-nanjing',
    profile: { httpProfile: { endpoint: 'scf.tencentcloudapi.com' } }
  })
  const target = { FunctionName: 'siss', Namespace: 'default' }
  const before = await client.GetFunction(target)
  if (before.Status !== 'Active') throw new Error(`函数当前状态为 ${before.Status}，无法安全更新`)
  const result = await client.UpdateFunctionCode({
    ...target,
    ZipFile: zip.toString('base64'),
    Publish: 'FALSE'
  })
  console.log(`已提交函数代码更新，请求 ID：${result.RequestId}`)
  for (let attempt = 0; attempt < 60; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 5000))
    const current = await client.GetFunction(target)
    if (current.Status === 'Active') {
      console.log('函数更新完成，状态正常')
      return
    }
    if (current.Status === 'UpdateFailed' || current.Status === 'CreateFailed') {
      throw new Error(`函数更新失败：${current.StatusDesc || current.Status}`)
    }
    console.log(`等待函数更新：${current.Status}`)
  }
  throw new Error('等待函数更新超时，请到腾讯云控制台检查函数状态')
}

main().catch(error => {
  console.error(error.message)
  process.exitCode = 1
})
