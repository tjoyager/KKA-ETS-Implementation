"""
main.py
=======
File eksekusi utama untuk proyek simulasi robot gudang berbasis kecerdasan buatan (KKA).

Fitur Utama:
- Menu interaktif ramah pemula (cukup jalankan: python main.py).
- Perbandingan dua algoritma Informed Search: A* Search vs Greedy Best-First Search (GBFS).
- Visualisasi 3D interaktif menggunakan Ursina Engine dengan fitur ganti rute langsung di layar.
- Dukungan argumen command-line opsional (--no-gui, --algo, --heuristic, --diagonal).
"""

import argparse
import sys
from typing import Dict

from src.map_grid import WarehouseGrid
from src.algorithms import (
    a_star_search,
    greedy_best_first_search,
    manhattan_distance,
    euclidean_distance,
    SearchResult,
)
from src.simulation_3d import run_3d_simulation


def print_banner():
    banner = r"""
===================================================================
      SIMULASI ROBOT GUDANG 3D - KECERDASAN BUATAN (KKA)
         Navigasi Informed Search: A* Search vs GBFS
===================================================================
"""
    print(banner)


def format_table_row(cols, widths):
    formatted = []
    for c, w in zip(cols, widths):
        formatted.append(str(c).ljust(w))
    return "| " + " | ".join(formatted) + " |"


def print_comparison_table(results: Dict[str, SearchResult]):
    """Mencetak tabel perbandingan metrik kinerja antar algoritma."""
    headers = [
        "Algoritma",
        "Status",
        "Panjang Rute",
        "Total Biaya",
        "Simpul Dieksplorasi",
        "Waktu (ms)",
    ]
    widths = [26, 10, 14, 13, 21, 12]
    separator = "+" + "+".join(["-" * (w + 2) for w in widths]) + "+"

    print("\nTABEL PERBANDINGAN METRIK KINERJA:")
    print(separator)
    print(format_table_row(headers, widths))
    print(separator)

    for name, res in results.items():
        status_str = "SUKSES" if res.success else "GAGAL"
        row = [
            name,
            status_str,
            f"{res.path_length} sel",
            f"{res.cost:.2f}",
            f"{res.nodes_explored} simpul",
            f"{res.execution_time_ms:.4f}",
        ]
        print(format_table_row(row, widths))

    print(separator)


def print_analysis(results: Dict[str, SearchResult]):
    """Menampilkan analisis teoritis komprehensif terkait hasil pencarian."""
    res_a = results.get("A* Search")
    res_g = results.get("Greedy Best-First Search")

    if not (res_a and res_g and res_a.success and res_g.success):
        return

    print("\nANALISIS TEORITIS KKA:")
    if res_a.cost < res_g.cost:
        diff_cost = res_g.cost - res_a.cost
        print(
            f"  [+] Optimalitas : A* menemukan rute LEBIH OPTIMAL (biaya {res_a.cost:.1f} vs {res_g.cost:.1f})."
        )
        print(
            f"                    GBFS terjebak mengambil rute memutar lebih jauh (+{diff_cost:.1f} biaya) karena hanya mengandalkan nilai heuristik h(n)."
        )
    else:
        print(f"  [+] Optimalitas : Kedua algoritma menghasilkan panjang rute yang sama ({res_a.cost:.1f}).")

    if res_g.nodes_explored < res_a.nodes_explored:
        print(
            f"  [+] Efisiensi   : GBFS mengeksplorasi LEBIH SEDIKIT simpul ({res_g.nodes_explored} vs {res_a.nodes_explored} simpul)."
        )
        print(
            "                    GBFS fokus langsung ke arah target (greedy), sedangkan A* meneliti simpul alternatif untuk menjamin keoptimalan rute."
        )
    else:
        print(
            f"  [+] Efisiensi   : A* mengeksplorasi {res_a.nodes_explored} simpul, sedangkan GBFS mengeksplorasi {res_g.nodes_explored} simpul."
        )


def launch_gui(warehouse: WarehouseGrid, results: Dict[str, SearchResult], initial_algo: str = "A* Search"):
    """Meluncurkan visualisasi 3D dengan instruksi yang ramah pengguna."""
    print("\n" + "=" * 65)
    print("MELUNCURKAN VISUALISASI 3D URSINA ENGINE...")
    print("=" * 65)
    print("Kontrol Interaktif dalam Jendela 3D:")
    print("  - [Klik Tombol UI] : Tombol kontrol tersedia langsung di bagian bawah layar")
    print("  - [Tab]            : Beralih rute secara langsung antara A* Search dan GBFS")
    print("  - [Spasi]          : Jeda (Pause) / Lanjutkan pergerakan robot AGV")
    print("  - [R]              : Reset posisi robot ke titik awal")
    print("  - [V]              : Ganti sudut kamera (Isometrik / Tampak Atas / Bebas)")
    print("  - [+/-]            : Atur kecepatan pergerakan robot")
    print("  - [Esc]            : Menutup jendela 3D dan kembali ke terminal")
    print("=" * 65 + "\n")

    try:
        run_3d_simulation(
            grid_map=warehouse,
            results_or_path=results,
            active_algo=initial_algo,
            auto_start=True,
        )
    except Exception as e:
        print(f"\n[Catatan] Jendela visualisasi 3D telah ditutup ({e}).")


def main():
    parser = argparse.ArgumentParser(
        description="Simulasi Robot Gudang 3D dengan Algoritma Informed Search (KKA)"
    )
    parser.add_argument(
        "--algo",
        choices=["astar", "gbfs", "compare"],
        default=None,
        help="Algoritma awal yang ditampilkan (astar / gbfs / compare)",
    )
    parser.add_argument(
        "--heuristic",
        choices=["manhattan", "euclidean"],
        default="manhattan",
        help="Fungsi heuristik yang digunakan (default: manhattan)",
    )
    parser.add_argument(
        "--diagonal",
        action="store_true",
        help="Aktifkan pergerakan diagonal 8-arah (default: False / 4-arah)",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Jalankan dalam mode terminal saja tanpa membuka visualisasi 3D",
    )

    args = parser.parse_args()

    # Pilih fungsi heuristik
    heuristic_func = manhattan_distance if args.heuristic == "manhattan" else euclidean_distance
    heuristic_name = "Manhattan Distance" if args.heuristic == "manhattan" else "Euclidean Distance"

    # Inisialisasi peta denah gudang default
    warehouse = WarehouseGrid.create_default_warehouse()

    # Hitung rute untuk kedua algoritma
    results: Dict[str, SearchResult] = {
        "A* Search": a_star_search(
            warehouse,
            heuristic=heuristic_func,
            allow_diagonal=args.diagonal,
        ),
        "Greedy Best-First Search": greedy_best_first_search(
            warehouse,
            heuristic=heuristic_func,
            allow_diagonal=args.diagonal,
        ),
    }

    # Jika argumen CLI eksplisit diberikan (misal --no-gui atau --algo)
    is_cli_mode = args.no_gui or (args.algo is not None)

    if is_cli_mode:
        print_banner()
        print(f"Dimensi Peta Gudang : {warehouse.width} x {warehouse.height} sel")
        print(f"Posisi Start (S)    : {warehouse.start}")
        print(f"Posisi Goal  (G)    : {warehouse.goal}")
        print(f"Fungsi Heuristik    : {heuristic_name}")
        print(f"Pergerakan Diagonal : {'Aktif (8-arah)' if args.diagonal else 'Nonaktif (4-arah)'}")

        print_comparison_table(results)
        print_analysis(results)

        chosen_algo = "A* Search"
        if args.algo == "gbfs":
            chosen_algo = "Greedy Best-First Search"

        print(f"\nPeta Rute ({chosen_algo}):")
        warehouse.print_ascii_map(results[chosen_algo].path)

        if not args.no_gui:
            launch_gui(warehouse, results, initial_algo=chosen_algo)
        return

    # =========================================================================
    # MENU INTERAKTIF RAMAH PEMULA (DEFAULT KETIKA 'python main.py' DIJALANKAN)
    # =========================================================================
    print_banner()
    print("Selamat datang di Program Simulasi Robot Gudang 3D!")
    print(f"Denah Gudang: {warehouse.width}x{warehouse.height} sel | Start: {warehouse.start} | Goal: {warehouse.goal}")
    print("\nSilakan pilih mode yang ingin dijalankan:")
    print("  [1] Buka Visualisasi 3D Interaktif (Bisa ganti A* & GBFS di dalam jendela 3D) [Rekomendasi]")
    print("  [2] Tampilkan Tabel Perbandingan & Analisis Teori KKA di Terminal")
    print("  [3] Mode Terminal Saja (Tampilkan Peta ASCII & Metrik tanpa GUI)")
    print("  [4] Keluar")

    choice = "1"
    if sys.stdin.isatty():
        try:
            user_input = input("\nMasukkan pilihan Anda [1-4] (Tekan ENTER untuk Opsi 1): ").strip()
            if user_input:
                choice = user_input
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar program.")
            return
    else:
        # Menangani input yang di-pipe (misal: echo "3" | python main.py)
        try:
            line = sys.stdin.readline().strip()
            if line:
                choice = line
        except (KeyboardInterrupt, EOFError):
            pass

    if choice == "1":
        # Langsung buka jendela 3D dengan A* Search sebagai rute default
        launch_gui(warehouse, results, initial_algo="A* Search")

    elif choice == "2":
        # Tampilkan tabel lengkap di terminal, lalu tawarkan membuka 3D
        print("\nPETA DENAH GUDANG 2D:")
        print("Keterangan: [S]=Start, [G]=Goal, [#]=Rak/Rintangan, [.]=Lorong Kosong")
        warehouse.print_ascii_map()
        print_comparison_table(results)
        print_analysis(results)

        print("\nPETA JALUR OPTIMAL (A* SEARCH):")
        warehouse.print_ascii_map(results["A* Search"].path)

        if sys.stdin.isatty():
            try:
                open_3d = input("\nApakah Anda ingin membuka Visualisasi 3D sekarang? [Y/n]: ").strip().lower()
                if open_3d in ("", "y", "ya", "yes"):
                    launch_gui(warehouse, results, initial_algo="A* Search")
            except (KeyboardInterrupt, EOFError):
                pass

    elif choice == "3":
        # Cetak peta ASCII dan metrik perbandingan saja
        print("\nPETA DENAH GUDANG 2D:")
        warehouse.print_ascii_map()
        print_comparison_table(results)
        print_analysis(results)
        print("\nPeta Jalur A* Search:")
        warehouse.print_ascii_map(results["A* Search"].path)
        print("\nPeta Jalur GBFS:")
        warehouse.print_ascii_map(results["Greedy Best-First Search"].path)

    elif choice == "4":
        print("\nTerima kasih telah menggunakan program simulasi robot gudang 3D!\n")
        return

    else:
        print(f"\nPilihan '{choice}' tidak dikenali. Menjalankan Visualisasi 3D default...")
        launch_gui(warehouse, results, initial_algo="A* Search")


if __name__ == "__main__":
    main()
