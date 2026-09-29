# Thực nghiệm model nhỏ: tra từ + quiz thích ứng

- **qwen2.5:7b-instruct-q4_K_M** — nạp 17.8s — `qwen2.5:7b-instruct-q4_K_M 845dbda0ea48 5.1 GB 18%/82% CPU/GPU 4096 29 minutes from now`
- **gemma2:2b** — nạp 112.7s — `gemma2:2b 8ccf136fdd52 1.9 GB 100% GPU 4096 29 minutes from now`
- **llama3.2:3b** — nạp 20.7s — `llama3.2:3b a80c4f17acd5 2.6 GB 100% GPU 4096 29 minutes from now`
- **qwen2.5:3b-instruct-q4_K_M** — nạp 12.0s — `qwen2.5:3b-instruct-q4_K_M 357c53fb659c 2.2 GB 100% GPU 4096 29 minutes from now`

## Tra từ

| chỉ số | qwen2.5:7b-instruct-q4_K_M | llama3.2:3b | qwen2.5:3b-instruct-q4_K_M |
|---|---|---|---|
| n | 80 | 80 | 80 |
| success | 100% | 98% | 74% |
| top1 | 79% | 55% | 51% |
| top3 | 79% | 56% | 54% |
| foreign | 1 | 0 | 9 |
| french | 0 | 0 | 0 |
| stable | 25% | 12% | 15% |
| mean_s | 9.9 | 4.3 | 36.0 |
| p95_s | 13.87 | 4.85 | 122.66 |
| ipa | 100% | 100% | 100% |
| tags | {'academic': '75%', 'common': '100%', 'edge': '100%', 'edge_injection': '100%', 'inflected': '100%', 'phrase': '90%', 'polysemy': '66%'} | {'academic': '62%', 'common': '100%', 'edge': '100%', 'edge_injection': '100%', 'inflected': '100%', 'phrase': '40%', 'polysemy': '28%'} | {'academic': '75%', 'common': '50%', 'edge': '50%', 'edge_injection': '0%', 'inflected': '62%', 'phrase': '80%', 'polysemy': '31%'} |
| errors | [] | ['ai_bad_output'] | ['ollama_timeout'] |

## Quiz thích ứng

| chỉ số | qwen2.5:7b-instruct-q4_K_M | llama3.2:3b | qwen2.5:3b-instruct-q4_K_M |
|---|---|---|---|
| n | 13 | 13 | 13 |
| success | 100% | 100% | 100% |
| fill | 96% | 75% | 51% |
| full | 92% | 62% | 15% |
| four_opts | 98% | 100% | 100% |
| unique_opts | 98% | 80% | 62% |
| explanation | 100% | 100% | 100% |
| copies_learner | 6% | 0% | 11% |
| foreign | 0 | 0 | 0 |
| key_agree_7b | 88% | 68% | 85% |
| judged | 49 | 41 | 26 |
| positions | [5, 32, 7, 5] | [8, 24, 9, 0] | [9, 11, 4, 2] |
| coverage | 100% | 105% | 100% |
| mean_s | 20.8 | 7.9 | 8.0 |
| p95_s | 24.91 | 9.9 | 9.92 |
| errors | [] | [] | [] |
