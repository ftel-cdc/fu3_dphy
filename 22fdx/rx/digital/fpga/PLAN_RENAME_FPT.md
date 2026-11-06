# Plan: đổi tiền tố module `m_ftel_` → `m_fpt_` theo quy tắc của team PD (2026-11-04)

> - Repo `fu3_dphy`, branch `dev`, HEAD `6138f79` (đã push; dòng TN2b ở §12 của `fpga/PLAN_EOT_NOWAIT.md` đã
>   commit lúc 10:41). Working tree sạch.
> - Ký hiệu: ✅ đã kiểm · ⚠️ ước lượng hoặc giả định · 🔍 kiểm khi làm.
> - Sau khi duyệt, bước P0 chép plan này vào `fpga/PLAN_RENAME_FPT.md`, theo lệ của `PLAN_EOT_NOWAIT.md`.

## 0. Context

- **Quy tắc PD (bạn gửi 04/11):** wrapper `logical/m_fpt_<ip>_wrap.sv`, `logical/filelist.f`,
  `sdc/constraint.sdc`, define `FPT_SIGNOFF`, tên dont-touch `u_`/`w_`/`i_`/`o_dont_touch_`, `<IP>_PATH`.
- **Flow của fu3 đọc cứng** ✅:
  - `$<IP>_PATH/logical/filelist.f` và `$<IP>_PATH/sdc/constraint.sdc` (`hw/asic/flow/dc/scripts/user_setup.tcl:70-71`);
  - tên top lấy từ bảng `<IP>(module_name) "m_fpt_<ip>_wrap"` (`:64`).

  Ở fu2 và fu3, `constraint.sdc` thường là symlink sang `m_fpt_<ip>_wrap.sdc` (adc, bus, cpu, crc, crm, dbg) ✅.
- **Bạn quyết (04/11):** đổi tên về `m_fpt_`, vì chỉ là tên, không đổi chức năng. Dùng lệnh để thay cho nhanh.
- **Phạm vi đo được** ✅:
  - 68 file đã track, 807 chỗ, 24 tên;
  - 25 file mang tên `m_ftel_`, cộng file sdc;
  - tất cả nằm trong `22fdx/rx/digital`; `req/rtm.json` chiếm 410 chỗ.

## 1. Quy tắc đổi tên

| Hiện tại | Mới | Ghi chú |
|---|---|---|
| `m_ftel_dphy_rx`, `m_ftel_dphy_rx_<block>`, `m_ftel_dphy_rx_wrap` | `m_fpt_dphy_rx`, `m_fpt_dphy_rx_<block>`, `m_fpt_dphy_rx_wrap` | `<ip>` = `dphy_rx`: token của port wrapper (rtl_rule N8) và của `--ip dphy_rx` trong tool_flow |
| `m_ftel_ppi_act_gate` (chỉ dùng ở FPGA, `fpga/rtl/`) | `m_fpt_ppi_act_gate` | Cùng một tiền tố cho cả repo |
| `sdc/m_ftel_dphy_rx_wrap.sdc` | `sdc/m_fpt_dphy_rx_wrap.sdc`, cộng symlink `sdc/constraint.sdc` → file này | Như fu2/fu3. `run_syn.sh`, `cdc.sgdc` và `rdc.sgdc` vẫn gọi file thật theo tên |

- **Không đổi:**
  - tên IP `ftel_dphy_rx`: thư mục, package `ftel_dphy_rx_*_pkg`, tên hình, doc id;
  - các biến `FTEL_DPHY_RX_PATH` và `FTEL_LIB_*`.

  Quy tắc PD chỉ đặt tên file wrapper; tên biến `<IP>_PATH` tùy `<ip_name>` mà PD chọn (§6).
- **Giữ nguyên văn (history):**
  - các dòng revision của `doc/spec.md`: dòng v0.3 ghi lần đổi sang tên FX1;
  - các dòng revision của `doc/rtl_rule.md`: dòng 1.2.
- **Sửa tay, không dùng `sed`:**
  - rtl_rule N1, câu "tiền tố FX1 là `m_ftel`", thành tiền tố `m_fpt` theo quy tắc PD của fu3, kèm nguồn;
    thêm dòng revision 1.3;
  - hàng "Module names" trong `README.md`.

## 2. Lệnh và file chính

- **Đổi tên file:** `git mv` 25 file, ví dụ `logical/m_ftel_dphy_rx_wrap.sv`, `syn/cells/m_ftel_dphy_rx_cg.sv`,
  `fpga/rtl/m_ftel_ppi_act_gate.sv`, cộng `sdc/m_ftel_dphy_rx_wrap.sdc`.
- **Đổi tên trong nội dung:** `sed -i 's/m_ftel_/m_fpt_/g'` trên các file `git grep -l m_ftel_` trả về.
  - Trừ `req/rtm.json`: file này do `flow_check.py` P3a sinh lại.
  - Trừ các dòng revision ở §1: dùng address của `sed` (`/^| v0\.[0-9]* (draft) |/!`) hoặc khôi phục đúng các
    dòng đó.
  - Trước khi ghi: chạy thử và liệt kê mọi dòng `.md` sẽ đổi.
- **`ip_config.yaml`:** thêm `top_module: m_fpt_dphy_rx_wrap`. Lý do: mặc định của tool_flow là
  `naming.ip_module: "m_ftel_{ip}_wrap"` (`ip-dev/hw/utils/tool_flow/config/project.yaml`), và key này được
  phép (`run_ip_tool.py:160, 292`).
- **Các file chạm nhiều:**
  - `logical/filelist.f`, `syn/dc_syn.tcl`, `syn/run_syn.sh`, `sim/vcs_lint.sh`;
  - `req_flow/check_rtl_rules.py` (`MODULE_RE`, `CORE, WRAP`, selftest) và `req_flow/flow_check.py` (selftest);
  - bench `fpga/exp1/tb_exp1.sv`, `fpga/exp2/tb_exp2a.sv`, `fpga/exp2b/tb_exp2b.sv`, `exp2b.tcl`, `fpga/rtl/*`;
  - `tn2a_evidence.py` và `tn2b_evidence.py`: check `copy` so code của hai bench, nên hai bên đổi cùng lúc.
- **Script so:** chuyển `compare_pre.py`, hiện chỉ có trong scratchpad, vào `fpga/tools/compare_runs.py`.
  - Thêm option `--pre <tên>` và `--ignore <regex cột>`.
  - Ở plan này dùng `--pre _pre_rename`, không bỏ cột nào: đổi tên thì mọi cột phải trùng, kể cả `stopstate`.
  - Nhờ vậy cổng so của 03/11 cũng chạy lại được.

## 3. Bước, cổng, ước lượng ⚠️

| Bước | Việc | Cổng: sai thì dừng và báo | Ước lượng |
|---|---|---|---|
| P0 | Chép plan vào `fpga/PLAN_RENAME_FPT.md` | - | 0,02 ngày |
| 1 | Chép run hiện tại (RTL v0.17, chạy 03/11) sang `fpga/work/{exp1,exp2,exp2b}/_pre_rename/` (khoảng 2,6 GB, đĩa trống 156 GB ✅); làm `fpga/tools/compare_runs.py` | So `_pre_rename` với chính nó ra 0 khác | 0,05 ngày |
| 2 | Đổi tên theo §1-2; symlink `constraint.sdc`; `ip_config.yaml`; sửa tay N1 và README | `git grep -n m_ftel_` chỉ còn các dòng history của §1 | 0,15 ngày |
| 3 | Kiểm tĩnh: `check_rtl_rules` (selftest + 22 file); VCS lint với 1, 2, 4 lane và chế độ 1; SpyGlass `lint_rtl` qua tool_flow; `flow_check` P2, P3a; DC `syn/run_syn.sh` | 0 vi phạm, 0 xung đột; `rtm.json` mới trùng bản cũ sau khi thay `m_ftel_`→`m_fpt_`; DC: diện tích 5948 µm², 2646 flop, WNS/TNS từng góc như 03/11; netlist trùng bản cũ sau cùng phép thay | 0,15 ngày + khoảng 10 phút máy |
| 4 | Chạy lại ở nền, 2 luồng như 03/11: A = TN1 `all model skew report window lowgap drain`; B = TN2a `all model neg`, rồi TN2b `shim finding`; build lại từ đầu | Mọi file dữ liệu của 458 run trùng từng byte với `_pre_rename`, kể cả `stopstate` (`tb.txt` có tên module nên không so); evidence TN1 9/9, TN2a 10/10, TN2b 12/12; các evselftest PASS | 0,05 ngày công + khoảng 3,2 giờ máy (luồng B) |
| 5 | HAS v0.18: K6 nhắc tên wrapper, cộng dòng revision "no technical change"; đăng ký `EXPECTED` v0.18 (số bảng không đổi); resync P1 (dự kiến 1 REQ đổi chữ) | P1/P2/P3a 0 xung đột; `check_spec` 0, `check_figures` 0 (hình không có tên module ✅); docx XSD PASS | 0,15 ngày |
| 6 | Tài liệu: `TN1_DESCRIPTION` 1.3, `TN2_DESCRIPTION` 1.2 (sửa luôn dòng RTL "HAS v0.16" đã sai), `TN2_REPORT` 1.1 (thêm lần chạy lại 03/11 và 04/11), `TN3_SPEC`, `doc/sync/questions_csi_team.md`, các README, D-29 trong `doc/rtl_notes.md`, `req/spec_review.md` §7.18, memory | Quét token 0; không em/en dash | 0,15 ngày |

- **Tổng:** khoảng 0,7 ngày công + 3,2 giờ máy ⚠️. Bước 5 và 6 làm trong lúc bước 4 chạy.
- **Commit, chỉ khi bạn bảo:**
  1. `refactor:` RTL, script, bench, checker, sdc, req, HAS v0.18, các plan và README nội bộ;
  2. `docs:` tài liệu bàn giao.

## 4. Rủi ro

1. **`sed` đổi chỗ không được đổi:** dòng history, hay câu trích cấu hình tool_flow. Chạy thử và liệt kê
   trước (§2); hiện chưa thấy dạng `m_ftel_{` nào ✅.
2. **Cache build** trong `fpga/work` còn trỏ tên cũ: build lại từ đầu ở bước 4.
3. **Kết quả khác** ở rtm, netlist hay capture: dừng và phân tích. Đổi tên đúng nghĩa thì không có khác biệt nào.
4. **Ngoài phạm vi:** repo DPHY (fallback) và build S0 ở đó giữ tên cũ. Team FPGA và team CSI đang cầm tài liệu
   có tên cũ, nên dòng phiên bản ghi lần đổi tên.

## 5. Kiểm chứng end-to-end

- **Không còn tên cũ:** `git grep m_ftel_` chỉ còn các dòng history; `git status` thấy 26 file rename.
- **Chức năng không đổi:**
  - rtm và netlist DC trùng sau khi thay tên;
  - 458 run trùng từng byte;
  - evidence và evselftest như cũ.
- **Flow sạch:** lint, rule checker, P1/P2/P3a, `check_spec`, `check_figures`, docx.
- **Đúng quy tắc PD:** `logical/m_fpt_dphy_rx_wrap.sv`, `logical/filelist.f`, `sdc/constraint.sdc`, và
  `readlink sdc/constraint.sdc` = `m_fpt_dphy_rx_wrap.sdc`.

## 6. Ngoài plan: câu hỏi cho team PD, bạn quyết

- **`<ip_name>` trong fu3:** plan giả định `dphy_rx`. Nếu PD chọn tên khác thì chạy `sed` thêm một lần. Tên biến
  môi trường cũng theo đó: `DPHY_RX_PATH` hay `FTEL_DPHY_RX_PATH`?
- **Cách đưa IP vào fu3:** fu3 gắn mỗi IP bằng submodule có gốc repo là gốc IP ✅. IP mình nằm ở
  `22fdx/rx/digital` trong repo công khai.
- **Hai cell clock khi có `FPT_SIGNOFF`:**
  - flow PD đọc nguyên filelist, nên nhận bản hành vi;
  - `set_dont_touch u_dont_touch*` có thể để logic trong đó không được map ⚠️;
  - `m_fpt_lib_cg` của fu3 không có `i_scan_en`, trong khi bản của fu2 có ✅.

  Việc này đổi RTL, nên cần plan riêng sau khi hỏi PD.
- **Define:** `ifndef SYNTHESIS` hay `FPT_SIGNOFF`. Formality có tự define `SYNTHESIS` không thì 🔍.
- **Dont-touch** cho sampler đặt tay (HAS §4.3); đơn vị thời gian của lib, vì sdc mặc định ps.

## 7. Độ tin cậy

- **HIGH:** phạm vi đo được, các điểm đọc cứng của flow fu3, cách đổi bằng lệnh và các cổng kiểm.
- **MED:** ước lượng công; số REQ phải resync ở bước 5.

## 8. Phát hiện khi làm (2026-11-04)

1. **`sdc/constraint.sdc` đã có sẵn:** một symlink chưa track, tạo lúc 15:13, trỏ sang tên sdc cũ. Sau khi đổi
   tên, symlink gãy. Đã trỏ lại sang `m_fpt_dphy_rx_wrap.sdc` và `git add`.
2. **507 run, không phải 458:** §3 quên 49 run `lowgap`/`drain` của TN1 (24 + 24 + NEG-drain). `_pre_rename` giữ
   cả 507: TN1 407 (279 + 128 `window`), TN2a 60, TN2b 40. Đây là các run có `args.txt` ghi từ 16:00 ngày 03/11.
   Các run cũ hơn (`LG-E2a3`, `DBG-*` và `S0` của 22/10) không được chạy lại nên không đem so.
3. **File không so được từng byte:**
   - `xsim.log`, `rss.txt` và `*.vcd` mang giờ, đường dẫn hoặc dung lượng bộ nhớ;
   - `tb.txt` của TN2b mang tên module;
   - `args.txt` có dòng `sources <hash>`, dòng này đổi vì mã nguồn đổi.

   `compare_runs.py` bỏ qua nhóm thứ nhất, so `tb.txt` sau `--subst m_ftel_=m_fpt_`, và bỏ dòng `sources`
   (`--drop-lines`). Mọi file dữ liệu khác, kể cả mọi cột CSV, phải trùng.
4. **Project Vivado giữ tên file cũ:** `.prj` của mỗi build ghi 20 hoặc 21 file `m_ftel_*.sv`. Runner chỉ tạo lại
   project khi file tcl mới hơn `elaborate.sh`. Đã `touch` `exp1.tcl`, `exp2.tcl` và `exp2b.tcl`; nội dung
   không đổi. Mỗi build tốn thêm khoảng 2 phút.
5. **Luật `NAME` của `validate_req.py` coi `m_fpt_` là tên bị thay,** vì lần đổi tên ở v0.3 đi theo chiều ngược
   lại. Lần validate đầu báo đúng 1 lỗi ở REQ-302. Đã đảo luật: tên bị thay nay là `m_ftel_`. Đây là cập nhật luật
   theo quyết định đổi tên, không phải nới luật.
6. **Không so được output DC theo từng dòng:**
   - DC ngắt dòng netlist ở độ rộng cố định và đệm cột report theo tên dài nhất, mà `m_fpt_` ngắn hơn `m_ftel_`
     một ký tự;
   - so sau khi bỏ khoảng trắng và gộp các đường kẻ `-`: 72/72 file trùng, gồm 68 report và 4 netlist;
   - `write_sdc` chỉ khác ở dòng ngày "Created by write_sdc on".

   Output DC tên cũ của 03/11 vẫn nằm lại trong `syn/netlist` (gitignored); bản để so ở `syn/work/_pre_rename/`.
   Cả hai, cùng `fpga/work/*/_pre_rename/`, đã xoá ngày 2026-11-05 ([`PLAN_PD_SIGNOFF.md`](PLAN_PD_SIGNOFF.md) §10).
7. **Package cấu hình sinh lại** chỉ khác dòng HAS v0.17 → v0.18 ở header. P3a báo CF-DRIFT vì package đổi sau
   lint, nên đã chạy lại VCS lint và SpyGlass. Đó là đúng hành vi của cổng.

## 9. Kết quả (2026-11-04)

- **P0, bước 1:** plan đã chép; `fpga/tools/compare_runs.py` mới (`--copy --since`, `--ignore-cols`,
  `--drop-lines`, `--subst`; run chưa chạy lại thì không đạt). So `_pre_rename` với chính nó: 0 khác ở cả 507 run.
  Dựng lại cổng của 03/11 trên TN2b bằng script mới: 0 khác, `stopstate` khác ở 39 run, như hôm đó.
- **Bước 2:**
  - 25 file `git mv`; nội dung sửa ở 67 file;
  - `sdc/constraint.sdc` → `m_fpt_dphy_rx_wrap.sdc`; `ip_config.yaml` thêm `top_module`;
  - rtl_rule 1.3 (N1, nguồn 2 mới); hàng "Module names" của README;
  - `git grep m_ftel_` chỉ còn các dòng lịch sử và các câu cố ý nhắc tên cũ: dòng revision v0.3 của spec, dòng 1.2
    của rtl_rule, luật `NAME`, ghi chú phiên bản của tài liệu bàn giao, D-29.
- **Bước 3:**
  - `check_rtl_rules` 0 vi phạm trên 22 file, selftest 57/57;
  - VCS 0/0/0 ở 1, 2, 4 lane và chế độ 1; SpyGlass 0/0/0 với top `m_fpt_dphy_rx_wrap`;
  - P1/P2/P3a 0 xung đột; `rtm.json` trùng ở `requirements` và `summary`;
  - DC trùng như mục 6 ở trên; diện tích 5948 µm², 2646 flop.
- **Bước 4:** đạt ✅. Luồng A (TN1) chạy 15:44 đến 16:45, luồng B (TN2a rồi TN2b) 15:44 đến 18:55, build lại từ đầu.
  - `compare_runs.py --pre _pre_rename --drop-lines '^sources ' --subst m_ftel_=m_fpt_`, mọi cột kể cả `stopstate`:
    TN1 407 run (2442 file), TN2a 60 run (486 file), TN2b 40 run (449 file); 0 khác, 0 run chưa chạy lại.
  - Evidence: TN1 9/9, TN2a 10/10, TN2b 12/12; evselftest của cả ba PASS.
- **Bước 5:**
  - HAS v0.18: K6 và dòng revision;
  - `EXPECTED` v0.18 đăng ký trước;
  - P1 resync: 1 REQ viết lại (REQ-302), 0 mới, 0 retire;
  - `check_spec` 0, `check_figures` 0; docx XSD PASS;
  - chi tiết ở `req/spec_review.md` §7.18.
- **Bước 6:** đã sửa `TN1_DESCRIPTION` 1.3, `TN2_DESCRIPTION` 1.2 (dòng RTL ở §2 nay đúng), `TN3_SPEC` v0.3,
  câu hỏi cho team CSI, `fpga/README.md`, D-29 và ghi chú fu3 ở D-23 trong `doc/rtl_notes.md`. `TN1_REPORT` và
  `TN2_REPORT` ghi lần chạy lại này cùng lần chạy lại sau `fpga/PLAN_PD_SIGNOFF.md`, khi lần đó xong.
