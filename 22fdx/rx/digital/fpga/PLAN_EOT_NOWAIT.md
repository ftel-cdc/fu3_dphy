<!-- Bản lưu trong repo của plan đã được duyệt ngày 2026-11-03 (plan mode); nguồn: ~/.claude/plans/c-nh-ng-l-n-k-snuggly-pike.md. -->

# Plan: lane không chờ EoT done (ADR-006) và tham số `PARA_STOP_DRAIN_EN` cho `stopstate_x` (2026-11-03)

> - Repo `fu3_dphy`, branch `dev`, HEAD `51c021a`. Working tree đã có phần B: 4 file RTL, chưa commit.
> - Ký hiệu: ✅ đã kiểm · ⚠️ ước lượng hoặc giả định · 🔍 kiểm khi làm.
> - Sau khi duyệt, bước P0 chép plan này vào `fpga/PLAN_EOT_NOWAIT.md`.

## 0. Context

**Vì sao có plan này:**
- Tester của team FPGA chỉ ra một mâu thuẫn: Table 1-3 hứa 80-1792 Mb/s, còn §4.5 lại để lane bỏ burst dưới khoảng 240 Mb/s. Tester đề nghị làm luôn phương án ở dòng 606-610 của spec, ngay trong RX.
- **Vì sao việc này bị để ngỏ** (transcript ngày 29/09, commit `ce79709`): không phải vì hiệu suất.
  - Bạn chọn (b) "giữ chờ" theo quy tắc không tự quyết việc chạm tới team khác.
  - Một giờ sau mới biết (b) cũng chạm team CSI.
  - Bạn yêu cầu tìm phương án không phụ thuộc hoặc chuyển đổi nhanh, rồi gác lại để làm docx. Từ đó chưa ai làm tiếp.

**Bạn đã quyết (03/11):**
- Sửa ngay trong RX.
- Chọn **C-param**: mặc định là B, cộng một tham số để chọn `stopstate_x` "sau khi delay line xả hết".
- Giữ file `m_fpt_dphy_rx_tsync.sv`, chỉ bỏ khỏi filelist.

**Đã làm và đo, phần B** ✅ (THS-EXIT + TLPX tối thiểu, mỗi run 32 burst × 4 lane):

| Rate (Mb/s) | Trước | Sau | Trailer | Khe `rxactivehs_x` giữa 2 burst | `stopstate_x` trước byte cuối |
|---|---|---|---|---|---|
| 80 | 16/32 | 32/32 | 0..1 | 3-4 byte clock (300-400 ns) | 34-35 byte clock |
| 120 / 160 | 16/32 / 24/32 | 32/32 | 0 / 0..2 | 5-7 | 33-35 |
| 200 / 260 | 32/32 | 32/32 | 0 | 8-12 (trùng run cũ) | 32-33 |
| 400 → 1792 | đủ | 32/32 | 0 | 330-340 ns | 30 → 11-13 |

- Thêm 7 run với THS-PREPARE + THS-ZERO tối thiểu và THS-TRAIL tối thiểu: đều 32/32.
- Rule checker 0 vi phạm. VCS lint PASS ở 1, 2 và 4 lane.
- Số liệu nằm ở `fpga/work/exp1/NW-*`.

## 1. Thiết kế

### 1.1 Phần B (đã có trong working tree ✅)

- `m_fpt_dphy_rx_dl_ctrl.sv`:
  - `DL_HS_EOT` chỉ còn 1 cycle: gặp LP-00 thì sang `DL_HS_WAIT` (HS RX timeout, đường truyền còn ở HS), còn lại sang `DL_STOP`;
  - bỏ `i_eot_done` và `reg_eot_lp00`.
- `m_fpt_dphy_rx_hs_datapath.sv`: bỏ `o_eot_done`, khối tsync, `i_core_clk` và `i_core_rst_n`.
- `m_fpt_dphy_rx.sv`: bỏ các dây tương ứng.
- `filelist.f`: bỏ dòng tsync; file .sv giữ nguyên.
- Enum giữ nguyên, nên mã trạng thái xuất ra status không đổi.

### 1.2 C-param (mới)

**Tham số `PARA_STOP_DRAIN_EN`:**
- Mặc định 0; là dòng #11 của Table 3-1.
- Đi theo đúng flow:
  - `config/ftel_dphy_rx.yaml`;
  - `config/validate_config.py`: thêm vào `SYN_KEYS`, thêm luật mới CFG-17 (giá trị ∈ {0, 1});
  - sinh lại `ftel_dphy_rx_config_pkg.sv`, không sửa tay.
- Đường đi: wrapper → core → `dl_ctrl`.

**RTL, chỉ dùng cell và cờ đã có:**
- `m_fpt_dphy_rx_eot.sv`: thêm output `o_line_busy` = OR các cờ active và skew-cal của delay line.
- `m_fpt_dphy_rx_hs_datapath.sv`: thêm `reg_busy <= w_start || line_busy`, là thanh ghi nguồn của crossing; ra `o_hs_busy`.
- `m_fpt_dphy_rx_dl_ctrl.sv`:
  - `i_hs_busy` đi qua `m_fpt_dphy_rx_sync` (2 flop, `core_clk`), có tag `CDC_CROSSING: byte -> core`;
  - `reg_stopstate <= (w_state_nxt == DL_STOP) && !((PARA_STOP_DRAIN_EN != 0) && w_hs_busy)`.
- Không dùng `generate`. Với giá trị 0, phép AND là hằng, nên synthesis bỏ phần busy; về chức năng thì giống hệt B.

**Hành vi khi bằng 1** (mô phỏng lại từ capture ⚠️, sẽ đo trên RTL thật):
- `stopstate_x` lên 1-2 byte clock + khoảng 15 ns sau byte HS cuối, tính cả `rxskewcalhs_x`.
- Không có xung giữa hai burst sát nhau, tới 1440 Mb/s.
- Phụ thuộc byte clock giống đuôi dữ liệu (S12): mất clock lúc delay line chưa xả hết thì `stopstate_x` kẹt Low.

## 2. Bench, checker, evidence

- **`fpga/exp1/tb_exp1.sv`:** tham số `STOP_DRAIN` (mặc định 0) nối vào `.PARA_STOP_DRAIN_EN`.
- **`fpga/exp1/run_exp1.sh`:**
  - build stub thứ hai `build_stub_drain`, dùng `-generic_top STOP_DRAIN=1`;
  - target `lowgap`: 24 run của bảng trên (MAXTR theo rate);
  - target `drain`: cùng 24 run trên build drain, thêm phép kiểm `stopstate_x`.
- **`fpga/tools/csi2_dump.py`, mode `bursts`:**
  - option `--stop-drain D`, cho được theo từng capture như `--max-trailer`. Hai điều kiện:
    1. ở mẫu nào `stopstate` High thì `rxactivehs`/`rxskewcalhs` không High trong [i, i + D];
    2. `stopstate` High ở cuối capture.
  - Thêm một dòng chỉ ghi nhận: số khe trên đường truyền có `stopstate` High.
  - Selftest: capture S1 sạch phải PASS; `stopstate` lên giữa burst phải FAIL.
  - NEG thật: lấy một run `lowgap` (mặc định) kiểm bằng `--stop-drain`, phải FAIL.
- **`fpga/exp1/tn1_evidence.py`:**
  - mục mới `lowgap`, tự giải mã: đủ burst, payload đúng, trailer trong giới hạn; với run drain thì tự tính lại hai điều kiện `stopstate`;
  - `evselftest` thêm 2 lỗi cài: mất một burst; `stopstate` lên giữa burst.
- **`sim/vcs_lint.sh`:** thêm một lần chạy wrapper với `PARA_STOP_DRAIN_EN` = 1.

## 3. Hồi quy (ngoài `stopstate`, không cái gì được đổi)

- **Chép trước để so:** `work/exp1`, `work/exp2`, `work/exp2b` sang `work/*/_pre_nowait/`, khoảng 2,7 GB, không xoá gì.
- **Chạy lại** (đường build mới, chạy nền, tối đa 2 luồng vì RAM trống 17 GB và máy dùng chung):
  - TN1: `all`, `model`, `skew`, `report`, `window`, khoảng 1 giờ máy;
  - TN2a: `all`, `model`, khoảng 1-1,5 giờ ⚠️;
  - TN2b: `shim`, `finding`, khoảng 45 phút.
- **Cổng:**
  - mọi kết luận của check, evidence và evselftest giữ nguyên;
  - so với `_pre_nowait`: mọi cột PPI **trừ `stopstate`** trùng từng byte, `frames.txt` của TN2b trùng từng byte;
  - khác ở bất kỳ chỗ nào khác thì dừng và phân tích.
- **Lint và syn:**
  - SpyGlass `lint_rtl` qua tool_flow;
  - DC `syn/run_syn.sh` mặc định: timing met ở 1792 và 1500 Mb/s, diện tích không tăng;
  - `flow_check` P3a.

## 4. HAS v0.17, req flow, docx (theo skill ftel-spec)

- **Đăng ký `EXPECTED` v0.17 trước khi sửa:**
  - Table 3-1 thêm 1 dòng;
  - Table 4-2 vẫn 11 dòng: bỏ EoT done, thêm HS busy;
  - các bảng khác giữ nguyên; số OPEN 🔍 tính khi đăng ký.
- **Các chỗ sửa:**
  - dòng revision v0.17;
  - Table 3-1 #11, Table 4-2, Table 4-5 (`DL_HS_EOT`);
  - §4.5: phần text và design note, ghi quyết định, số đo và hai chế độ;
  - §4.6: bỏ EoT done; sửa câu "start lên lại trong lúc hold" cho đúng. Với `hs_settle_cyc` của Appendix B, start Low ít nhất khoảng 5 byte clock, nên hold luôn xong trước;
  - §5.1 (`stopstate_x`, chế độ 1), §5.2 (EoT), danh sách verify ở §8;
  - ADR-006, Table 9-1.
  - Table 1-3 giữ nguyên, vì giờ đã đúng.
- **Hình** (skill ftel-block-diagram và ftel-waveform: render + `check_figures`):
  - 4-5, 4-6, 4-8, 4-9 và hình top;
  - 5-1: thêm hàng `stopstate_x` khi tham số = 1;
  - 5-9.
- **Req flow:**
  - resync P1: `rebase_req.py` → worklist → delta chunk (có `prev_req_id`) → `assemble_req.py` → `validate_req.py`;
  - P2: `validate_config.py --emit` và `--check-pkg`;
  - P3a;
  - gắn tag REQ mới vào RTL và package; dòng `HAS` trong header các file RTL đã sửa đổi thành v0.17.
- **Kiểm và build:** `check_spec.py`; `md2docx.py --validate` (docx chỉ build ở máy, không commit).
- **`doc/rtl_notes.md`:** thêm D-28 (không chờ, C-param); sửa dòng EoT done ở D-26; cập nhật bảng lint.

## 5. Tài liệu cho team khác (không dùng ID nội bộ)

- `doc/sync/questions_tx_side.md` S5: bỏ mục THS-EXIT + TLPX.
- `doc/sync/questions_csi_team.md`, phần EoT:
  - câu 1 sửa số: khoảng 36 byte clock ở mặc định, và giới thiệu tham số;
  - thêm câu về khe `rxactivehs_x` 330-400 ns giữa hai burst.
- `fpga/exp1/TN1_DESCRIPTION.md`, `TN1_REPORT.md`, `README.md`: thêm `lowgap` và `drain`.
- `fpga/README.md`: các lệnh mới.
- `exp2/TN2_*`: chỉ sửa nếu số liệu đổi.
- Memory.

## 6. Bước, cổng, ước lượng ⚠️

| Bước | Việc | Cổng: sai thì dừng và báo | Ước lượng |
|---|---|---|---|
| P0 | Chép plan vào `fpga/PLAN_EOT_NOWAIT.md` | - | 0,05 ngày |
| 1 | RTL C-param, YAML và generator; lint và rule checker (VCS 1/2/4 lane + chế độ 1) | 0 vi phạm, trừ tag REQ còn chờ resync | 0,3 ngày |
| 2 | Bench, checker, evidence; chạy `lowgap` và `drain` | 48/48 run PASS; NEG drain FAIL đúng chỗ; selftest và evselftest PASS | 0,5 ngày |
| 3 | Hồi quy nền, SpyGlass, DC | Theo §3 | 0,25 ngày công + khoảng 3 giờ máy |
| 4 | HAS v0.17, hình, req flow, docx | P1/P2/P3a 0 xung đột; `check_figures` 0 | 0,75 ngày |
| 5 | Tài liệu cho team khác, rtl_notes, README, memory | Quét token ra 0 | 0,25 ngày |

- Bước 3 chạy song song với bước 4 và 5.
- Commit chỉ khi bạn bảo. Đề xuất 2 commit: (1) RTL + bench + HAS + req; (2) tài liệu bàn giao.

## 7. Rủi ro

1. **Hồi quy khác ở chỗ ngoài `stopstate`:** dừng, xem đó là lỗi của RTL hay của bench, rồi báo.
2. **Controller AMD trong TN2b phản ứng với `stopstate_x` sớm hơn 3-4 byte clock:** báo lại. `frames.txt` phải trùng.
3. **SpyGlass báo về phần busy khi tham số = 0 (phép AND hằng):** xử lý trong flow, hoặc waiver có lý do. Không sửa RTL chỉ để tool im.
4. **`EXPECTED` v0.17 lệch so với dự kiến:** dừng và tìm nguyên nhân, không chỉnh số cho qua.

## 8. Ngoài plan

- SpyGlass CDC/RDC: chưa từng chạy cho IP này.
- Độ sâu delay line theo tốc độ.
- Gửi câu hỏi cho team CSI và phía Tx, trả lời tester: bạn quyết.
- TN2c, TN3.

## 9. Kiểm chứng end-to-end

- **Hai chế độ của RTL:**
  - `run_exp1.sh lowgap`: 24/24 PASS;
  - `run_exp1.sh drain`: 24/24 PASS cùng `--stop-drain`;
  - NEG FAIL đúng chỗ.
- **Không thoái lui:**
  - TN1, TN2a, TN2b chạy lại có cùng kết luận;
  - mọi cột PPI ngoài `stopstate` và `frames.txt` trùng từng byte với `_pre_nowait`.
- **Hai lớp độc lập:** `csi2_dump` và `tn1_evidence` cùng kết luận; evselftest bắt đủ lỗi cài.
- **Flow sạch:**
  - P1/P2/P3a 0 xung đột;
  - VCS lint, SpyGlass, `check_rtl_rules`, `check_spec`, `check_figures` đều 0;
  - DC timing met.

## 10. Độ tin cậy

- **HIGH:**
  - phần B: 24 run, lint, rule checker;
  - chế độ 1 dùng cell và cờ đã có.
- **MED:**
  - hành vi của chế độ 1: mới mô phỏng lại từ capture;
  - ước lượng công;
  - SpyGlass trên phần busy.
- **LOW:** thời gian máy chính xác của TN2a.

## 11. Phát hiện khi làm (2026-11-03)

1. **Figure 4-9 của v0.16 có một tầng thanh ghi ra không có thật.** §4.6 và RTL đều lấy output PPI từ entry cũ nhất.
   v0.17 bỏ tầng đó và ghi vào dòng revision.
2. **Option của bộ so** là `--stopstate lane|drain:<D>`, không phải `--stop-drain D` như §2: một option cho cả chế độ
   chỉ báo cáo (`lane`, run LG-*) và chế độ kiểm (`drain:32`, run DR-* và NEG-drain).
3. **Run RTL cũ ở 180 và 220 Mb/s báo hỏng vì trailer, không vì mất burst.** Lúc đó script chưa có bảng giới hạn
   trailer theo rate, nên dùng mặc định 1 byte. Số burst vẫn đủ, và số byte trailer trùng RTL mới. Ở 80, 120 và 160
   Mb/s, mọi burst RTL cũ nhận được đều đúng payload và không có cờ lỗi.
4. **Chế độ 1 không có xung Stop giữa hai burst sát nhau dưới 1792 Mb/s:** 0/124 khe ở 80-1500 Mb/s, 124/124 ở 1792.
   Lane rời Stop để nhận burst sau trước khi burst trước ra hết PPI. Chế độ 0 có xung ở mọi khe; ở 80 Mb/s capture
   chỉ thấy 108/124, vì nó lấy mẫu theo byte clock. Đây là số liệu cho câu hỏi gửi team CSI, không phải lỗi.
5. **Check `copy` của TN2a và TN2b hỏng sau khi `tb_exp1.sv` có thêm `STOP_DRAIN`.**
   - Evidence TN2a lần đầu cho 9/10, trong khi capture trùng hoàn toàn: instance của TN1 có thêm
     `.PARA_STOP_DRAIN_EN(STOP_DRAIN)`.
   - Sửa trong script kiểm chứng, không đụng bench TN2: `tn1_code_lines()` của `tn2a_evidence.py` bỏ kết nối đó
     trước khi so, và chỉ bỏ khi `STOP_DRAIN` còn mặc định 0. `tn2b_evidence.py` dùng chung hàm này.
   - Đã thử ngược: cho `STOP_DRAIN` mặc định 1 trong một bản copy của `tb_exp1.sv` thì `copy` FAIL.
   - `exp2/README.md` và `exp2/TN2_DESCRIPTION.md` (bản 1.1) ghi ngoại lệ này. Việc này không có trong plan.
6. **CFG-17 thiếu ca âm.** `validate_config.py --selftest-negative` cho 27/28 FAIL ("every constraint has a negative
   test"), thấy ở lần kiểm cuối. Đã thêm ca `STOP_DRAIN_EN 2`: 29/29. P2 và P3a chạy lại, 0 xung đột.
7. **RTL đổi trước spec,** ngược thứ tự thường lệ (đăng ký scope trước khi viết RTL). `req/rtl_scope.json` ghi điều
   này trong history.
8. **`tn2a_evidence.py evselftest <thư mục tương đối>`** báo FAIL ở mọi ca, kể cả ca sạch, vì symlink trong thư mục
   tạm trỏ theo đường dẫn tương đối. Chạy không đối số, như tài liệu hướng dẫn, hoặc với đường dẫn tuyệt đối thì
   PASS. Chưa sửa script.

## 12. Kết quả (2026-11-03)

- **Bước 1, RTL:**
  - `PARA_STOP_DRAIN_EN` đi từ YAML qua package sinh ra, wrapper và core tới `dl_ctrl`. HS busy nằm trong `_eot` và
    `_hs_datapath`;
  - VCS 0/0/0 cho 1, 2, 4 lane và cho chế độ 1; `check_rtl_rules` 0 vi phạm trên 22 file;
  - SpyGlass `lint_rtl` 0/0/0 ở giá trị mặc định, không thêm waiver. Rủi ro 3 không xảy ra.
- **Bước 2, bench:**
  - `lowgap` 24/24 PASS và `drain` 24/24 PASS. NEG-drain FAIL đúng chỗ: payload đúng, chỉ luật `stopstate` hỏng,
    mỗi lane một lỗi;
  - selftest của `csi2_dump.py` PASS; `tn1_evidence.py` 9/9; `evselftest` PASS với 18 lỗi cài.
- **Bước 3, hồi quy:**

  | Bộ | Run | So với `_pre_nowait` | Kiểm chứng |
  |---|---|---|---|
  | TN1 | 358: 230 run và 128 run của `window` | 0 khác ngoài `stopstate`; `stopstate` khác ở cả 358 | `tn1_evidence.py` 9/9, `evselftest` PASS |
  | TN2a | 60 | 0 khác ngoài `stopstate`; `stopstate` khác ở 59, trừ NEG-front (RX mình không nhận burst nào) | `tn2a_evidence.py` 10/10, `evselftest` PASS (1 ca sạch, 12 lỗi), `selftest` PASS |
  | TN2b | 40: 31 qua khối chỉnh, 9 của phát hiện | 0 khác ngoài `stopstate`, kể cả `frames.txt`; `stopstate` khác ở 39, trừ SH_NEG-front (RX mình không nhận burst nào) | `tn2b_evidence.py` 12/12, `evselftest` PASS (1 ca sạch, 19 lỗi) |

  DC ở giá trị mặc định: TNS 0, WNS như cũ trừ `core_clk` ở một góc kém 3 ps; diện tích 5990 → 5948 µm², flop
  2666 → 2646. Chế độ 1 chưa tổng hợp.
- **Bước 4, HAS v0.17:**
  - `EXPECTED` khớp dự kiến, nên rủi ro 4 không xảy ra;
  - P1, P2, P3a 0 xung đột; 378 REQ;
  - `check_spec` 0, `check_figures` 0;
  - docx 90 trang, XSD PASS, đã xem các trang có hình đổi.

  Chi tiết ở `req/spec_review.md` §7.17.
- **Bước 5, tài liệu:**
  - `doc/sync/questions_tx_side.md` S5 và `doc/sync/questions_csi_team.md` (câu 1 viết lại, câu 4 mới);
  - `exp1/TN1_DESCRIPTION.md` và `exp1/TN1_REPORT.md` bản 1.2, `exp1/README.md`, `fpga/README.md`;
  - D-28 trong `doc/rtl_notes.md`, memory;
  - quét token: 0 trên 56 file sẽ commit.
- **Khác với plan:**
  - tên option của bộ so (§11 mục 2);
  - script kiểm chứng TN2 sửa, và `TN2_DESCRIPTION.md` sửa dù số liệu không đổi, vì câu "lấy nguyên văn" không còn
    đúng từng chữ (§11 mục 5);
  - §7 của `TN1_REPORT.md` cũ ghi TN2 chưa làm, nay sửa;
  - `_pre_nowait` nặng 1,1 GB, không phải 2,7 GB như ước lượng;
  - thời gian máy: luồng A (TN1 và DC) 1 giờ; luồng B (TN2a rồi TN2b) 3,2 giờ. TN2a mất 1,5 giờ, trong ước lượng;
    TN2b mất 1,7 giờ, không phải khoảng 45 phút: 40 run chạy tuần tự, mỗi run 2-3 phút.
- **Còn mở, bạn quyết:**
  - gửi câu hỏi cho team CSI và phía Tx, trả lời tester;
  - deskew ở chế độ 1 chưa mô phỏng; thứ tự `rxskewcalhs_x` / `stopstate_x` mới suy từ cấu trúc (MED);
  - chế độ 1 chưa qua SpyGlass và DC.
