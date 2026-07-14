-- Tarifas oficiales revisadas el 2026-07-14. El SQL reproduce la tabla usada en
-- el informe; no consulta internet ni convierte estas tarifas en valores permanentes.
WITH assumptions AS (
    SELECT 8000.0 AS input_tokens, 1200.0 AS output_tokens
), rates(provider, service_type, input_usd_per_mtok, output_usd_per_mtok,
        source_url, quality_status) AS (
    VALUES
      ('Anthropic Haiku 4.5', 'Hosted reliability fallback', 1.0, 5.0,
       'https://www.anthropic.com/claude/haiku',
       'Pendiente de corpus Noesis'),
      ('Groq Qwen3 32B', 'Hosted pay-per-use', 0.29, 0.59,
       'https://groq.com/pricing', 'Pendiente de corpus Noesis'),
      ('Groq Llama 3.3 70B', 'Hosted pay-per-use', 0.59, 0.79,
       'https://groq.com/pricing', 'Pendiente de corpus Noesis'),
      ('Cloudflare Qwen3 30B A3B', 'Hosted pay-per-use', 0.051, 0.335,
       'https://developers.cloudflare.com/workers-ai/platform/pricing/',
       'Pendiente de corpus Noesis')
), costs AS (
    SELECT rates.*, assumptions.input_tokens, assumptions.output_tokens,
           (assumptions.input_tokens * rates.input_usd_per_mtok
            + assumptions.output_tokens * rates.output_usd_per_mtok) / 1000000.0
             AS cost_per_message_usd
    FROM rates CROSS JOIN assumptions
)
SELECT provider, service_type, input_usd_per_mtok, output_usd_per_mtok,
       CAST(input_tokens AS INTEGER) AS input_tokens,
       CAST(output_tokens AS INTEGER) AS output_tokens,
       ROUND(cost_per_message_usd, 6) AS cost_per_message_usd,
       ROUND(cost_per_message_usd * 75, 3) AS cost_75_usd,
       ROUND(cost_per_message_usd * 300, 3) AS cost_300_usd,
       ROUND(cost_per_message_usd * 1500, 3) AS cost_1500_usd,
       source_url, quality_status
FROM costs
ORDER BY cost_300_usd ASC;
