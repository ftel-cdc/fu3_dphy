# Plan: kiểm C6 và C10 ở PPI trong các checker của TN1/TN2 (2026-10-26)

> Repo `fu3_dphy`, branch `dev`, sau commit `e456f21`; thư mục `22fdx/rx/digital/fpga/`.
> Ký hiệu: ✅ đã kiểm · ⚠️ ước lượng hoặc giả định · 🔍 kiểm khi làm.
> Plan này đi trước [`PLAN_TN2B_GATE.md`](PLAN_TN2B_GATE.md) (phương án A của TN2b), để lần chạy lại TN2b dùng luôn checker
> mới. Duyệt ngày 2026-10-26.

## 0. Context

Một tester của team FPGA đang kiểm lại RTL và bench. Anh ấy sửa một bản sao capture rồi đưa cho checker:

| Triệu chứng | Input đưa vào checker | Kỳ vọng | Đo được |
|---|---|---|---|
| C6: lọt sai độ rộng hoặc vị trí của sync | Bản sao capture có sync HIGH 3 cycle, hoặc sync trễ tới byte payload thứ ba | Sync HIGH đúng 1 cycle, trùng byte đầu, nên checker phải FAIL | Checker gốc (`csi2_dump.py`) và decoder của evidence vẫn PASS, 0 lỗi |
| C10: lọt lệch lane | Bản sao capture có cả lane 3 trễ 8 cycle | Giới hạn ≤ 6 cycle, nên checker phải FAIL | Checker gốc, decoder của evidence và check ghép burst theo thời gian đều PASS |

Anh ấy hỏi thêm: RTL có kiểm soát được lệch giữa các lane không, và nếu vượt 6 byte clock thì spec bảo xử lý thế nào?

## 1. Đánh giá

| # | Dữ kiện | Nguồn |
|---|---|---|
| E1 | **C6:** `decode_bursts` đếm *cạnh lên* của `rxsynchs` trong mỗi burst, và `check_bursts` đòi đúng 1 cạnh. Sync rộng 3 cycle hay sync trễ vẫn chỉ có 1 cạnh, nên lọt. Không có chỗ nào so vị trí sync với byte đầu. Mode `ppi` (TN2b) không đọc cột sync | ✅ [`tools/csi2_dump.py`](tools/csi2_dump.py) |
| E2 | **C10:** mỗi lane chỉ ghép với truth của chính lane đó, dung sai bằng nửa khoảng cách nhỏ nhất giữa hai burst (cỡ µs). `decode_ppi` ghép byte của các lane theo thứ tự. Không có phép so nào giữa các lane | ✅ cùng file |
| E3 | `exp1/tn1_evidence.py` không có self-test cài lỗi; TN2a và TN2b có. Check của nó chỉ đòi hai bộ giải mã **cùng kết luận**, không đòi mọi kịch bản **PASS** (check `runs` của TN2a thì có đòi). HAS §8 hứa một "PPI monitor" kiểm quan hệ của Figure 5-1 đến 5-8 ở mọi burst, nhưng chưa có. C10 thì HAS giao cho bước tích hợp với RTL của controller CSI-2 | ✅ đọc code; [`../doc/spec.md`](../doc/spec.md) §8 |
| E4 | **RTL đúng ở mọi burst đã chạy.** ftel: 28 274 burst theo lane (TN1 14 752, TN2a 7 816, TN2b 5 706). Mỗi burst có đúng 1 sync rộng 1 cycle, cùng cycle với byte đầu. 280 burst ở TN2b là hai run chẩn đoán, nơi TB cố ý dời sync. D-PHY AMD: sync rộng 1, trước byte đầu 1 cycle. Lệch giữa các lane (byte đầu và lúc `rxactivehs` lên) bằng 0 ở mọi burst nhiều lane, cả hai receiver | ✅ đo trên capture đã lưu, 2026-10-26 |
| E5 | **Skew lớn nhất đã thử là 139 ps (0,2 UI).** Generator đặt skew bằng transport delay trên từng lane, mọi giá trị đều được, truth cũng dời theo, nên chạy được với skew vài byte mà không sửa SV | ✅ [`exp1/dphy_line_gen.sv`](exp1/dphy_line_gen.sv) |
| E6 | Tài liệu đã giao team FPGA ghi đúng điều đang kiểm ("`rxsynchs` lên đúng một lần"), nhưng điều đó yếu hơn C6, và C10 không được nhắc | ✅ [`exp1/TN1_DESCRIPTION.md`](exp1/TN1_DESCRIPTION.md) |

**Kết luận:**
- Cả hai triệu chứng là lỗ hổng *của checker* (verification gap), không phải lỗi RTL.
- **Câu hỏi về C10:**
  - RTL xử lý từng lane độc lập và không căn lại các lane, nên lệch ở PPI chính là skew của link tính theo byte clock.
  - Giới hạn 6 là ngân sách của controller CSI-2: khi vượt, FIFO của lane trong controller đầy và burst bị bỏ, theo HAS của controller.
  - HAS của mình chưa nói rõ điều này: đây là trường hợp "chưa định nghĩa rõ".
  - Các run E1-6 ở §2 sẽ đo quan hệ đó bằng run thật.

## 2. Sửa gì

**`tools/csi2_dump.py`, dùng chung cho mode `bursts` (TN1, TN2a) và `ppi` (TN2b):**
- **`--sync-at`:**
  - Mỗi burst của lane phải có đúng một sample có `rxsynchs` (đếm sample, không đếm cạnh).
  - Vị trí sync so với byte hợp lệ đầu tiên phải bằng giá trị cho trước: `0` (ftel, HAS C6), `-1` (D-PHY AMD, như ví dụ PPI của spec D-PHY), hoặc `-` (không kiểm).
  - Có thể cho danh sách theo từng capture, như `--max-trailer`.
- **`--max-lane-spread N`:**
  - Trong mỗi burst, với mỗi byte k mà mọi lane đều có, cycle tới của byte k ở các lane không lệch nhau quá N. Đây đúng là "inter-lane byte divergence" của C10, kể cả khi `rxvalidhs` có khe (C7).
  - TN1 và TN2a ghép các lane theo id burst của truth; TN2b ghép trong cùng cửa sổ burst.
- **Selftest:**
  - thêm đúng ba lỗi của tester (sync 3 cycle; sync ở byte thứ ba; lane 3 trễ 8): mỗi lỗi phải FAIL;
  - bản gốc phải PASS;
  - vị trí kiểu AMD phải PASS với `-1` và FAIL với `0`.

**Script:**
- `exp1/run_exp1.sh`, `exp2/run_exp2.sh`: truyền `--sync-at=-1,0 --max-lane-spread=6`.
- `exp2b/run_exp2b.sh`: như trên. Riêng hai run chẩn đoán `amd1`/`amd2`, R-F kỳ vọng `-1` vì TB dời sync. PPI của TX không có sync, nên dùng `-`.

**Evidence, lớp độc lập:**
- `tn1_evidence.py` (decoder này cũng được TN2a dùng) và `tn2b_evidence.py` tự tính lại C6 và C10 bằng code riêng.
- Check `runs` của TN1 đòi thêm: mọi kịch bản PASS trong `check.txt`, trừ NEG-skew, phải FAIL đúng ở lệch lane.
- **`tn1_evidence.py evselftest` mới**, theo mẫu TN2a/TN2b: cài từng lỗi vào bản sao run, rồi đòi đúng các check của lỗi đó FAIL. Có hai cách cài:
  - chỉ sửa capture: decoder của evidence phải không còn khớp với `check.txt`;
  - sửa capture rồi chạy lại `csi2_dump.py`, đúng như tester làm: checker gốc cũng phải báo FAIL.

  Các lỗi cài: ba lỗi của tester, một byte payload lật bit, một burst mất, một sync bị dời, và các lỗi trên file text như ở TN2a.
- `evselftest` của TN2a và TN2b: thêm ba lỗi của tester.

**Run TN1 mới** (target `skew` của `run_exp1.sh`, không sửa SV): 1440 Mb/s, 4 lane, `+LENS=1,4,64,256`, chỉ lane 3 có skew.

| Run | Skew | Kỳ vọng |
|---|---|---|
| E1-6a | 2,5 byte (13 889 ps) | Lệch 2–3; PASS |
| E1-6b | 5,5 byte (30 556 ps) | Lệch 5–6; PASS |
| NEG-skew | 7,5 byte (41 667 ps) | Payload PASS; **chỉ FAIL ở mục lệch lane**, cả hai receiver. Đây là thử âm thật, không phải capture bị sửa |

## 3. Chạy lại và kiểm

- **TN1 chạy lại đầy đủ trong fu3:** `all`, `model`, `report`, `skew`, `window`. Khoảng 1 giờ máy ⚠️.
  - Lý do: 227 run cũ nằm ở repo DPHY, mà check `sources` băm cả đường dẫn.
  - Chạy ở fu3 cũng cho team FPGA một mốc trùng với repo mà họ đang dùng.
- **TN2a, TN2b:** chỉ `recheck` (không mô phỏng lại), rồi `evidence` và `evselftest`.
- **Cổng:**
  - selftest của `csi2_dump` PASS;
  - mọi run cũ vẫn PASS với checker mới, đúng như số đo E4; riêng `amd1`/`amd2` PASS với kỳ vọng `-1`;
  - E1-6a/b PASS; NEG-skew FAIL đúng mục;
  - evidence của ba bench PASS;
  - evselftest bắt đủ lỗi đã cài;
  - số của TN1 chạy lại ở fu3 trùng với 227 run ở DPHY. Nếu khác thì báo, rồi sửa tài liệu bàn giao.

## 4. Docs

- `exp1/TN1_DESCRIPTION.md` và `exp1/TN1_REPORT.md` (đã giao team FPGA): bảng check thêm C6 và C10; kết quả mới; E1-6 và NEG-skew; evselftest. Không dùng ID nội bộ.
- `exp1/README.md`, `exp2/README.md`, `exp2b/README.md`: bảng check. `fpga/README.md`: lệnh mới.
- **HAS v0.17 (tuỳ chọn, làm sau cùng; có thể tách ra sau):** chỉ làm rõ, không đổi hành vi.
  - C10: ftel không căn lại các lane, nên lệch ở PPI là skew của link tính theo byte (số đo E1-6); trên ngân sách thì controller bỏ burst.
  - §8: nêu phần PPI monitor nào đã có.

## 5. Bước, cổng, ước lượng ⚠️

| Bước | Việc | Cổng: sai thì dừng và báo | Ước lượng |
|---|---|---|---|
| 1a | `csi2_dump.py` (C6, C10), selftest | Ba lỗi của tester FAIL, bản gốc PASS | 0,3 ngày |
| 1b | Script; evidence; `tn1_evidence evselftest`; target `skew` | Recheck TN2a/TN2b PASS; evselftest bắt đủ | 0,5 ngày |
| 1c | Chạy lại TN1 ở fu3, E1-6, NEG-skew; evidence ba bench | Theo §3 | 0,25 ngày |
| 1d | Docs | Quét token ra 0 | 0,25 ngày |
| 1e | *(tuỳ chọn)* HAS v0.17 | P1/P2/P3a 0 xung đột | 0,4 ngày |

Commit chỉ khi được bảo.

## 6. Độ tin cậy

- **HIGH:**
  - hai lỗ hổng là của checker (đọc code, khớp với cái tester làm);
  - RTL đạt C6 và C10 ở mọi burst đã chạy (28 274 burst).
- **MED:**
  - lệch lane ở E1-6 theo đúng skew (chưa chạy);
  - ước lượng công.

## 7. Kết quả (2026-10-26)

**Bước 1a–1d xong, mọi cổng đạt. 1e (HAS v0.17) chưa làm, chờ bạn quyết.**

**1a, `tools/csi2_dump.py`:**
- `--sync-at` và `--max-lane-spread` có ở mode `bursts` và `ppi`.
- Selftest PASS, gồm:
  - ba lỗi của tester, mỗi lỗi ra đúng lỗi C6 hoặc C10;
  - cả ba lọt khi không bật hai tuỳ chọn, đúng như tester thấy;
  - sync kiểu AMD đạt với `-1`, hỏng với `0`.

**1b, script và evidence:**

| Bench | Recheck với checker mới | `evidence` | `evselftest` |
|---|---|---|---|
| TN2a | 60/60 run giữ nguyên kết luận | PASS 10/10 | PASS: 1 ca sạch, 12 lỗi (thêm ba lỗi của tester) |
| TN2b (39 run trước phần 2) | 39/39 run giữ nguyên kết luận; ở `amd1`/`amd2`, timing PPI của R-F đạt với kỳ vọng `-1` (TB dời sync) | PASS 11/11 | PASS: 1 ca sạch, 16 lỗi (thêm ba lỗi của tester) |

`tn1_evidence.py evselftest` mới: 1 ca sạch và 15 lỗi.
- Ba lỗi của tester có hai dạng: chỉ sửa capture (phải hỏng `decode`), và sửa rồi làm lại `check.txt` (phải hỏng `runs`).
- Các lỗi còn lại: byte lật, burst mất, kịch bản FAIL, NEG-skew PASS, thiếu run, front end, `term_en`,
  `eot_skip_bytes`, hash build.

**1c, chạy lại TN1 trong fu3** (5 lệnh nối tiếp, nice 10, 59 phút, chạy cùng TN2b):
- **230 run:** 229 PASS, NEG-skew FAIL đúng chỗ. Evidence PASS 8/8 (459/459 capture), evselftest PASS.
- **So với lần chạy 2026-10-20 ở repo DPHY:**
  - `truth.txt` và hai CSV của 227 run trùng từng byte (681/681 file); kết luận của 227 run như cũ;
  - 128 run `window` trùng (256/256 file); bảng `eot_window.py` giống hệt;
  - riêng hai run `window` vốn FAIL ở model + 2 (lane 1 mất trọn một burst) có thêm lỗi lệch lane ở các burst ghép
    lệch, kết luận không đổi;
  - các lỗi `rxsynchs` ở các run model + 2 có cả ở bộ so cũ ("0 times"): byte đầu và sync của nó bị cắt cùng nhau.
- **Timing ở PPI của mọi run:**
  - ftel đưa `rxsynchs` đúng một sample, cùng byte đầu (230 run); AMD trước một cycle (229 run);
  - lệch giữa các lane bằng 0 ở mọi run nhiều lane, kể cả E1-3d/e/f (139 ps).
- **E1-6, NEG-skew** (lane 3 trễ 2,5 / 5,5 / 7,5 byte time):

  | Run | AMD | ftel | Kết quả |
  |---|---|---|---|
  | E1-6a | 3 | 2–3 | PASS |
  | E1-6b | 6 | 5–6 | PASS |
  | NEG-skew | 8 | 7–8 | FAIL đúng chỗ: payload 16/16, 4 lỗi lệch lane ở mỗi RX |

  Số đo đúng quan hệ "lệch ở PPI = skew theo byte" của §1, ở cả hai RX (rủi ro 2 không xảy ra).

**1d, docs:**
- `exp1/TN1_DESCRIPTION.md` và `exp1/TN1_REPORT.md` lên bản 1.1;
- `exp1/README.md`, `exp2/README.md`; `exp2b/README.md` và `fpga/README.md` cập nhật cùng phần 2;
- quét token ra 0.

**Khác với plan:**
- `tn1_evidence.py evselftest` có 15 lỗi thay vì 6. Thêm dạng "làm lại `check.txt`" cho ba lỗi của tester, và các lỗi
  theo mẫu của TN2a/TN2b.
- Sửa thêm một lỗi có sẵn: `run_exp1.sh` không tham số in nhầm header bản quyền thay cho phần hướng dẫn.
- Lần chạy TN1 ở fu3 dùng nối tiếp 5 lệnh thay vì chia luồng, vì chạy cùng TN2b trên máy có tester dùng chung.
