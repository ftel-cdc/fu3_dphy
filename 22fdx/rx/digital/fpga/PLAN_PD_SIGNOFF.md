# Plan: filelist và hai cell clock theo flow sign-off của team PD (2026-11-04)

> - Repo `fu3_dphy`, branch `dev`, HEAD `7cbaa24`, chưa push (đổi tên `m_fpt_`).
> - Ký hiệu: ✅ đã kiểm · ⚠️ ước lượng hoặc giả định · 🔍 kiểm khi làm.
> - Sau khi duyệt, bước P0 chép plan này vào `fpga/PLAN_PD_SIGNOFF.md`.

## 0. Context

Tôi đã chạy flow DC của PD (chép từ fu3, chỉ thêm một dòng cho IP mình vào bảng, giữ option mặc định của
`run.csh`) trên IP mình, trong scratchpad, ngày 04/11. Kết quả có hai lỗ hổng so với quy tắc PD ✅:

1. **Biến đường dẫn.**
   - Flow PD chỉ export `<IP>_PATH`, còn filelist của mình dùng `${FTEL_DPHY_RX_PATH}`.
   - `analyze -vcs "-f"` của DC không thay biến viết dạng `${VAR}`, chỉ thay `$VAR`, nên `analyze` không
     đọc được file nào.
2. **Hai cell clock.**
   - Khi có `FPT_SIGNOFF`, flow PD nhận bản hành vi của hai cell, rồi đặt dont-touch lên chúng, nên còn
     8 cell chưa map (LINT-61).
   - Lần chạy thử, có nhánh `ifdef FPT_SIGNOFF` gọi `m_fpt_lib_cg` / `m_fpt_lib_clk_inv` của lib fu3 và thêm
     `-y $LIB_PATH/gate`, cho kết quả:
     - 0 cell chưa map;
     - setup dư 248 / 940 / 2852 ps (`ddr_clk` / `byte_clk` / `core_clk`), diện tích 6021 µm²;
     - 6 vi phạm removal từ -2.8 đến -6.6 ps trước CTS (D-30).

**Bạn quyết (04/11):** làm cả hai việc; `<ip_name>` do bên mình chốt, nên dùng `dphy_rx`.
- Biến là `DPHY_RX_PATH`. tool_flow đã export sẵn tên này và tìm IP bằng nó ✅ (`run_ip_tool.py`,
  `design_env_names` và `resolve_design_dir`).
- HAS không nói về filelist hay cách gắn cell, nên giữ nguyên v0.18 ✅.

## 1. Thay đổi

| Phần | Thay đổi |
|---|---|
| Biến | `FTEL_DPHY_RX_PATH` thành `DPHY_RX_PATH` ở mọi file (`git grep -l`, 48 chỗ). Riêng `fpga/PLAN_RENAME_FPT.md` là bản ghi plan nên giữ nguyên. Trong `logical/filelist.f` và `filelist_sim.f`, viết `$DPHY_RX_PATH`, không có ngoặc nhọn |
| Chỗ tự đọc filelist (12) | Cùng một mẫu, chỉ lấy dòng `.sv` bắt đầu bằng `$DPHY_RX_PATH`: `fpga/exp{1,2,2b}/exp*.tcl` (`string map` và bỏ mọi dòng không kết thúc bằng `.sv`); `run_exp{1,2,2b}.sh` (`sed 's#^\$DPHY_RX_PATH#...'`); `tn1/tn2a/tn2b_evidence.py` (`startswith('$DPHY_RX_PATH')`). `sim/vcs_lint.sh`, `sim/tb_afe_adapter/run.sh` và `syn/run_syn.sh` đã nhận cả hai dạng nên chỉ đổi tên biến |
| `logical/filelist.f` | Thêm `+libext+.v+.sv` và `-y $LIB_PATH/gate` (như filelist của IP adc trong fu3), kèm comment: dùng cho flow PD, `LIB_PATH` là lib của SoC; khi không có `FPT_SIGNOFF` thì không module nào được tìm ở đó |
| `logical/m_fpt_dphy_rx_cg.sv` | `` `ifdef FPT_SIGNOFF `` gọi `m_fpt_lib_cg u_lib_cg_0 (.i_clk, .i_en, .o_clk)`, có tag `REQ-343, REQ-344` (rule N6, T2). `` `else `` là bản hành vi hiện tại, giữ nguyên từng chữ. `i_scan_en` không dùng trong nhánh này, vì cell fu3 tự buộc test enable về Low; mình cũng buộc về 0 ✅ |
| `logical/m_fpt_dphy_rx_clk_inv.sv` | Như trên: `m_fpt_lib_clk_inv u_lib_clk_inv_0 (.i_in, .o_out)`, tag `REQ-339`. Port trùng hẳn ✅ |
| Không đổi | `syn/cells/` và cách `syn/run_syn.sh` thay file (flow riêng của mình, cell lấy tên từ `.env`); bench và mô phỏng không định nghĩa `FPT_SIGNOFF`, nên vẫn dùng bản hành vi |

Rule checker đọc cả hai nhánh `ifdef`. Hai instance mới đặt tên và tag đúng N6, T2, F6. Module `m_fpt_lib_*`
không nằm trong `CELL_PORTS` hay `CLK_CELLS`, nên K10 và K12 không bắt ✅ (`req_flow/check_rtl_rules.py:84-103`).

## 2. Bước, cổng, ước lượng ⚠️

| Bước | Việc | Cổng: sai thì dừng và báo | Ước lượng |
|---|---|---|---|
| S0 | Chờ luồng B (TN2b) xong, vì nó đang dùng `filelist.f`, `exp2b.tcl` và `run_exp2b.sh`. Chạy nốt cổng của lần đổi tên: so exp2, exp2b, evidence TN2a, TN2b. Điền §9 của `PLAN_RENAME_FPT.md` | 0 khác, evidence 10/10 và 12/12 | khoảng 19:00 + 0,05 ngày |
| P0 | Chép plan vào `fpga/PLAN_PD_SIGNOFF.md` | - | 0,02 ngày |
| 1 | Chép run vừa chạy lại sang `_pre_signoff` (`compare_runs.py --copy --since '2026-11-04 15:40'`, khoảng 1,1 GB) | So bản chép với chính nó ra 0 khác | 0,02 ngày |
| 2 | Sửa theo §1: dry run liệt kê mọi dòng sẽ đổi, rồi `sed`; hai cell sửa tay | `git grep FTEL_DPHY_RX_PATH` chỉ còn trong plan cũ | 0,1 ngày |
| 3a | **Thử `-y $LIB_PATH/gate` khi không có `LIB_PATH`** (máy public): SpyGlass `lint_rtl` và VCS qua tool_flow, chạy hai lần, có và không có `LIB_PATH` | 0/0/0 cả hai lần. Nếu không sạch thì dừng và báo kèm phương án, chưa tự chọn 🔍 | 0,05 ngày |
| 3b | `check_rtl_rules` (selftest + 22 file); VCS lint 1, 2, 4 lane và chế độ 1; `flow_check` P2, P3a (sinh lại `rtm.json`, cập nhật manifest lint); `validate_config` | 0 vi phạm, 0 xung đột | 0,05 ngày |
| 3c | DC của mình (`syn/run_syn.sh`) | 72/72 report trùng lần 04/11, sau khi bỏ khoảng trắng và ngày chạy | 10 phút máy |
| 3d | **Flow PD từ repo:** runner trong scratchpad trỏ `DPHY_RX_PATH` vào `22fdx/rx/digital`, có `LIB_PATH` của fu3, không có `FTEL_DPHY_RX_PATH`. Sau đó LEC của PD (`fm/scripts/run_lec_rtl_w_preDFT.tcl`: RTL có `FPT_SIGNOFF` so với netlist của lần DC đó, có SVF) | DC: 0 LINT-61, QoR bằng lần C. Formality: `Verification SUCCEEDED`, 0 failing, 0 aborted | 20 phút máy |
| 4 | Chạy lại ở nền, 2 luồng như trước. Bắt buộc, vì phép kiểm `sources` của evidence băm `logical/*.sv` và hai cell đã đổi | `compare_runs.py --pre _pre_signoff --drop-lines '^sources '`: 0 khác, 0 run chưa chạy lại (507 run); evidence TN1 9/9, TN2a 10/10, TN2b 12/12; các evselftest PASS | khoảng 3,5 giờ máy, chạy qua đêm |
| 5 | Tài liệu: `doc/rtl_rule.md` 1.4 (K10: nhánh `FPT_SIGNOFF`); `doc/rtl_notes.md` (D-23, D-29: biến và `<ip_name>`; D-30 mới với bốn lần chạy, kết quả 3d, các điểm báo PD); `README.md` (biến, đoạn tích hợp: `DPHY_RX_PATH`, `LIB_PATH`, `FPT_SIGNOFF`); `TN1_DESCRIPTION` 1.4 (dòng 45); `TN1_REPORT` và `TN2_REPORT` thêm lần chạy lại 04/11 (đổi tên và sign-off); `fpga/README`; memory | Quét token 0 (kể cả object sẽ push); không em/en dash; không tên cell PDK trong repo | 0,15 ngày |

- **Tổng:** khoảng 0,5 ngày công + 4 giờ máy ⚠️. Bước 5 làm trong lúc bước 4 chạy.
- **Commit, chỉ khi bạn bảo:**
  1. `feat:` filelist, hai cell, script, rtl_rule, rtl_notes, README, plan;
  2. `docs:` tài liệu bàn giao.

## 3. Rủi ro

1. **`-y` trỏ vào thư mục không có** làm lint public báo lỗi (bước 3a). Dừng và báo, không tự chọn cách lách.
2. **Cell fu3 đổi port** trong tương lai: nhánh `FPT_SIGNOFF` hỏng mà mô phỏng không thấy. Lần 3d bắt được
   lỗi này; D-30 ghi rõ phụ thuộc.
3. **Mô phỏng khác** ở bước 4: không được xảy ra, vì nhánh `else` giữ nguyên từng chữ. Nếu có khác thì dừng và
   phân tích.
4. **Repo public:** không chép code lib hay flow của fu3 vào repo; trong repo chỉ có tên module `m_fpt_lib_*`
   và tên biến. Các runner PD nằm trong scratchpad.

## 4. Báo team PD (bạn gửi; sau bước 3d)

- IP folder: `<ip_name>` = `dphy_rx`, biến `DPHY_RX_PATH`; dòng bảng `DPHY_RX(module_name) "m_fpt_dphy_rx_wrap"`.
- Filelist cần `LIB_PATH` của fu3 (`-y $LIB_PATH/gate`).
- **Kết quả DC và LEC trên flow của họ:**
  - removal vài ps trước CTS;
  - `-gate_clock` chèn clock gate trên các thanh ghi song song của miền DDR (đạt trước CTS);
  - lỗi `set ROM` của `setup_lib.tcl`.
- Vẫn mở: cách đưa thư mục IP vào fu3 (submodule có gốc là gốc IP); dont-touch cho sampler đặt tay (HAS §4.3).

## 5. Độ tin cậy

- **HIGH:** chẩn đoán và cách sửa đã chạy thử trên flow của PD; phạm vi `git grep` đo được.
- **MED:** bước 3a, vì chưa biết SpyGlass xử lý `-y` trỏ vào thư mục không có thế nào; thời gian máy.

## 8. Phát hiện khi làm

1. **Bước 3a không đạt với một filelist** (thử trước trên bản sao IP trong scratchpad, 04/11). SpyGlass
   `lint_rtl` qua tool_flow, khi `logical/filelist.f` có dòng `-y $LIB_PATH/gate`:

   | `LIB_PATH` | Kết quả |
   |---|---|
   | không đặt (máy public) | FATAL: `Environment Variable '$LIB_PATH' is not defined` |
   | trỏ vào thư mục không tồn tại | thêm 1 Warning `checkCMD_dirfile03` |
   | trỏ vào lib fu3 | trùng mốc: 3 message, 1 waive, 2 Info |

   **Bạn chọn (04/11): tách filelist.**
   - `logical/filelist_rtl.f` giữ thứ tự compile; đây là `filelist.f` cũ, chuyển bằng `git mv` để giữ history.
   - `logical/filelist.f` là filelist của flow PD: `+libext+.v+.sv`, `-y $LIB_PATH/gate`,
     `-f $DPHY_RX_PATH/logical/filelist_rtl.f`.
   - `ip_config.yaml` ghi đè `filelist` và `vcs.filelist.{rtl,cell}` bằng `logical/filelist_rtl.f` (tool_flow
     gộp bằng `deep_merge`).
   - `filelist_sim.f` gọi `filelist_rtl.f`.
   - 12 chỗ tự đọc filelist của mình đọc `filelist_rtl.f`.
2. **Đã thử trên bản sao với cấu trúc tách** ✅:
   - DC của PD đọc được `-f` lồng nhau có biến: elaborate xong, tìm thấy `m_fpt_lib_cg` và `m_fpt_lib_clk_inv`;
   - SpyGlass không có `LIB_PATH`: trùng mốc;
   - VCS qua tool_flow (`--tool vcs`): 0 Error/Warning/Lint, 21 file;
   - `check_rtl_rules`: 22 file, 0 vi phạm.

## 9. Kết quả

Bước 2 và 3 làm trong một git worktree ở scratchpad (cùng HEAD `7cbaa24`), vì luồng B (TN2b) còn chạy trên
working tree chính. Bạn bảo không chờ luồng B.

| Bước | Kết quả |
|---|---|
| 2 | Hai filelist, hai cell, `filelist_sim.f`, `ip_config.yaml`, 12 chỗ đọc filelist; `git grep FTEL_DPHY_RX_PATH` chỉ còn trong các plan và trong bảng lịch sử của D-30 ✅ |
| 3a | SpyGlass `lint_rtl` qua tool_flow, không có `LIB_PATH`: trùng mốc (3 message, 1 waive, 2 Info). VCS qua tool_flow (`--tool vcs`): 0 Error/Warning/Lint ✅ |
| 3b | `check_rtl_rules`: 22 file, 0 vi phạm; selftest 57/57. VCS lint: 1, 2, 4 lane và chế độ drain đều 0/0/0. `validate_config`: package đúng. `flow_check` P2, P3a (`review`): 0 xung đột, 304/304 REQ truy vết, 30 tag OPEN; `rtm.json` chỉ đổi hash của hai cell ✅ |
| 3c | `syn/run_syn.sh`: 4 run, 0 lỗi; 72 file report và netlist trùng lần 04/11 (đã bỏ khoảng trắng và ngày); 4 `qor.rpt` chỉ khác các dòng thời gian compile ✅ |
| 3d | Flow DC của PD, chỉ có `DPHY_RX_PATH` và `LIB_PATH`: 0 cell chưa map; QoR, diện tích, danh sách vi phạm trùng lần C; dont-touch chỉ khác tên instance `u_lib_cg_0`, `u_lib_clk_inv_0`. LEC của PD: Verification SUCCEEDED, 2854 điểm tương đương, 0 failing, 0 aborted ✅ |
| Chuyển sang working tree chính | Sau khi luồng B của lần đổi tên xong: 29 file chép từ worktree sang (`cmp` trùng); chạy lại 3a, 3b trên working tree chính: như trên, `rtm.json` trùng worktree; worktree đã gỡ ✅ |
| 4 | Luồng A (TN1) 18:58 đến 19:58, luồng B (TN2a rồi TN2b) 18:58 đến 22:04, build lại từ đầu. `compare_runs.py --pre _pre_signoff --drop-lines '^sources '`, mọi cột kể cả `stopstate`: TN1 407 run (2442 file), TN2a 60 run (486 file), TN2b 40 run (449 file); 0 khác, 0 run chưa chạy lại. Evidence: TN1 9/9, TN2a 10/10, TN2b 12/12, cùng số với các bảng trong report. evselftest PASS: TN1 1 ca sạch + 18 lỗi, TN2a 1 + 12, TN2b 1 + 19 ✅ |
| 5 | `TN1_REPORT` 1.3, `TN2_REPORT` 1.1, `TN1_DESCRIPTION` 1.4, `TN2_DESCRIPTION` 1.3 (§2), `exp1/README.md` (§6, §7), `exp2/README.md` (§6, §7), `exp2b/README.md` (§6.7 mới, §7), `fpga/README.md`, D-30. Quét: 0 em/en dash, 0 token trên 36 file đổi và trên object, message của `origin/main..dev` ✅ |

Ghi chú của bước 5:
- `TN2_REPORT` còn ở bản 1.0 (2026-10-26), nên chưa ghi lần chạy lại 2026-11-03, dù `TN2_DESCRIPTION` §2 đã trỏ tới
  nó. Bản 1.1 ghi cả ba lần chạy lại (2026-11-03, hai lần 2026-11-04) ở §5.5 mới.
- Khi viết, đo thêm trên bản lưu `_pre_nowait` và `_pre_rename` (cách `stopstate` đổi ở lần 2026-11-03):
  - TN2a và 36 run TN2b: mỗi xung lên sớm hơn 2-5 (TN2a) hoặc 3-5 (TN2b) byte clock, số xung không đổi;
  - ba run 260 Mb/s của TN2b (E2b-4a, SH_E2b-4a, SH_M_E2b-4a): với RTL cũ, xung Stop trong 34 khe giữa 35 burst
    ngắn hơn một mẫu (30,8 ns), lane 0 và 1 không thấy xung nào, lane 2 và 3 thấy 31/34; với RTL mới 34/34, rộng 3-4
    mẫu. Dữ liệu và `rxactivehs` không đổi. Ghi ở `TN2_REPORT` §5.5 và `exp2b/README.md` §6.7.
- `exp2/README.md` §7 ghi evselftest 2026-10-26 là "13 lỗi"; thật ra là 13 ca: 1 ca sạch và 12 lỗi, như `TN2_REPORT`
  ghi. Đã sửa.
- Thời gian máy: luồng A 1 giờ, luồng B 3,1 giờ, trong ước lượng 3,5 giờ.
