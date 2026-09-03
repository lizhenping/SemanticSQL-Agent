const base = "http://127.0.0.1:8090/v1";

async function main() {
  console.log("POST", base + "/chat/completions");
  const t0 = Date.now();
  const resp = await fetch(base + "/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer empty",
    },
    body: JSON.stringify({
      model: "Qwen3.8-27B",
      messages: [{ role: "user", content: "你好" }],
      max_tokens: 512,
    }),
  });

  console.log("HTTP status:", resp.status, `(${Date.now() - t0} ms)`);

  if (!resp.ok) {
    console.log("Error body:", (await resp.text()).slice(0, 1000));
    process.exit(1);
  }

  const data = await resp.json();
  const msg = data.choices?.[0]?.message;
  console.log("finish_reason:", data.choices?.[0]?.finish_reason);
  console.log("usage:", JSON.stringify(data.usage));
  console.log("--- 模型回复 ---");
  console.log(msg?.content);
}

main().catch((e) => {
  console.error("请求失败:", e.cause?.code || e.name, e.message);
  process.exit(1);
});
