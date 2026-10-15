# Bộ đếm cấu trúc câu (luật) trên câu thật UD English-EWT dev: 993 câu

**Độ chính xác loại câu: 740/993 (75%)**. Nhãn suy ra từ cây cú pháp do người chú thích (luật suy nhãn có sai số riêng).

## Ma trận nhầm lẫn (hàng = nhãn gold, cột = luật dự đoán)

| gold \ luật | simple | compound | complex | compound_complex | n | recall |
|---|---|---|---|---|---|---|
| simple | 565 | 23 | 18 | 0 | 606 | 93% |
| compound | 17 | 39 | 0 | 1 | 57 | 68% |
| complex | 151 | 11 | 119 | 8 | 289 | 41% |
| compound_complex | 2 | 16 | 6 | 17 | 41 | 41% |

## Cấu trúc nâng cao

| Cấu trúc | Gold dương | Precision | Recall |
|---|---|---|---|
| conditional | 47 | 87% | 100% |
| passive | 101 | 86% | 70% |
| relative_clause | 110 | 72% | 30% |
| question | 112 | 100% | 100% |

Câu bị loại: {'không phù hợp (đa gốc/rời rạc/quá ngắn-dài/không kết thúc bằng dấu câu)': 986, 'luật tách thành ≠1 câu': 22}

## Một số câu luật đoán sai

- "Today's incident proves that Sharon has lost his patience and his hope in peace." — gold: complex, luật: simple
- "Arafat's death creates a vacuum in Palestinian leadership that will not soon be filled." — gold: complex, luật: simple
- "Ash-Sharq al-Awsat reports that Fallujah was closed Tuesday in a general strike." — gold: complex, luật: simple
- "US troops there clashed with guerrillas in a fight that left one Iraqi dead." — gold: complex, luật: simple
- "Radical Shiite cleric Muqtada al-Sadr said the attack was "criminal" and that "the Zionists have left only one choice for the Arabs, that of fighting and jihad"." — gold: complex, luật: simple
- "This operation would only consolidate the terrorist acts in the world and would not bring peace to the region," the message claimed." — gold: complex, luật: simple
- "That's overstating it, I know." — gold: complex, luật: simple
- "Simplicity gave it that blessed, laudatory lack of clutter, the efficient and effective text-based ads, and the support of anyone with a dial-up connection." — gold: simple, luật: compound
- "Now Iran wants to turn the tables and is inviting cartoonists to do their best by depicting the Holocaust." — gold: complex, luật: simple
- ""They can freely write anything they like about our prophet, but if one raises doubts about the Holocaust he is either fined or sent to prison," he added." — gold: complex, luật: compound_complex
- "He added that around 1,100 cartoons were submitted by participants from more than 60 countries and that more than 200 are on show." — gold: complex, luật: simple
- "He said the top three cartoons will be announced on September 2, with the winners being awarded prizes of 12,000, 8,000 and 5,000 dollars respectively." — gold: complex, luật: simple
