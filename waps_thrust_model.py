"""Steady-state thrust sweep for a vessel fitted with WAPS."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import root


class Sail:
    def __init__(self, area, x, y, tech_params, technology):
        self.area = float(area)
        self.x = float(x)
        self.y = float(y)
        self.tech_params = tech_params
        self.technology = int(technology)


class SailArray:
    def __init__(self, sails):
        self.sails = list(sails)


class YachtParameters:
    def __init__(self):
        # Reference vessel and environment
        self.m = 45_000 * 10**3  # kg
        self.Iz = 3.5e11  # kg m^2
        self.rho_air = 1.225  # kg/m^3
        self.rho_water = 1025.0  # kg/m^3

        # Simplified aerodynamic coefficients
        self.CL_max = 1.2
        self.CD0 = 0.05
        self.k = 0.12

        # Rudder and geometry
        self.Ar = 55.0  # m^2
        self.xr = -60.0  # m, longitudinal rudder position
        self.lr = 4.0  # m
        self.length = 220.0  # m
        self.beam = 40.0  # m
        self.draft = 14.5  # m

        # Simplified damping coefficients
        self.Du = 9645.0  # kg/m; R_T(u) = Du*u^2
        self.Dv = 3_000_000.0  # kg/s
        self.Dr = 0.0


class YachtModel:
    def __init__(self, params):
        self.p = params

    def apparent_wind(self, u, v, Vw, beta_w):
        """Return apparent-wind speed and angle in body-fixed coordinates."""
        Vax = Vw * np.cos(beta_w) - u
        Vay = Vw * np.sin(beta_w) - v
        Va = np.hypot(Vax, Vay)
        beta_a = np.arctan2(Vay, Vax)
        return Va, beta_a

    def total_sail_forces(self, u, v, Vw, beta_w, sail_array):
        Va, beta_a = self.apparent_wind(u, v, Vw, beta_w)
        Fx_total = 0.0
        Fy_total = 0.0
        N_total = 0.0

        for sail in sail_array.sails:
            delta_s, lambda1, R_s, ks, sigma = sail.tech_params

            if sail.technology == 1:  # Soft sail
                alpha = beta_a - delta_s
                CL = self.p.CL_max * np.sin(2.0 * alpha)
            elif sail.technology == 2:  # Simplified rotor-sail coefficient model
                # The spin ratio is prescribed; this simplified model sets CL directly.
                CL = 2.0 * lambda1
            elif sail.technology == 3:  # Simplified suction sail
                alpha = beta_a - delta_s
                CL = self.p.CL_max * np.sin(2.0 * alpha) + ks * sigma
            else:
                raise ValueError(
                    f"Unsupported sail technology {sail.technology}; use 1, 2, or 3."
                )

            CD = self.p.CD0 + self.p.k * CL**2
            q = 0.5 * self.p.rho_air * Va**2
            lift = q * sail.area * CL
            drag = q * sail.area * CD

            # Force decomposition retained from the supplied model/report.
            Fx = lift * np.sin(beta_a) - drag * np.cos(beta_a)
            Fy = lift * np.cos(beta_a) + drag * np.sin(beta_a)
            moment = sail.x * Fy - sail.y * Fx

            Fx_total += Fx
            Fy_total += Fy
            N_total += moment

        return Fx_total, Fy_total, N_total

    def rudder_force(self, u, v, r, delta_r):
        u_eff = max(abs(u), 0.5)
        alpha_r = delta_r - (v - self.p.lr * r) / u_eff
        CLr = 2.0 * np.pi * alpha_r
        return 0.5 * self.p.rho_water * self.p.Ar * u**2 * CLr

    def steady_residual(self, z, u_d, Vw, beta_w, sail_array, Ne):
        v, delta_r = z
        r = 0.0  # constant-yaw-rate assumption

        _, Fy, Ns = self.total_sail_forces(u_d, v, Vw, beta_w, sail_array)
        Fr = self.rudder_force(u_d, v, r, delta_r)
        Nr = self.p.xr * Fr

        v_dot = (Fy + Fr - self.p.Dv * v) / self.p.m
        r_dot = (Ns + Nr + Ne - self.p.Dr * r) / self.p.Iz
        return np.array([v_dot, r_dot])


def solve_one_wind_case(yacht, u_d, Vw, beta_w, sail_array, Ne):
    """Solve sway/yaw equilibrium and estimate raw and usable engine thrust."""
    z0 = np.array([0.0, np.deg2rad(45.0)])  # initial guesses: v, rudder angle
    solution = root(
        yacht.steady_residual,
        z0,
        args=(u_d, Vw, beta_w, sail_array, Ne),
    )

    if not solution.success or not np.all(np.isfinite(solution.x)):
        return {
            "solver_success": False,
            "solver_message": str(solution.message),
            "v_ss_m_s": np.nan,
            "rudder_angle_rad": np.nan,
            "apparent_wind_m_s": np.nan,
            "apparent_wind_angle_rad": np.nan,
            "sail_Fx_N": np.nan,
            "sail_Fy_N": np.nan,
            "sail_yaw_moment_Nm": np.nan,
            "hull_resistance_N": yacht.p.Du * u_d**2,
            "engine_thrust_raw_N": np.nan,
            "engine_thrust_used_N": np.nan,
            "residual_sway": np.nan,
            "residual_yaw": np.nan,
        }

    v_ss, delta_r_ss = solution.x
    residual = yacht.steady_residual(
        solution.x, u_d, Vw, beta_w, sail_array, Ne
    )
    Fx, Fy, Ns = yacht.total_sail_forces(u_d, v_ss, Vw, beta_w, sail_array)
    Va, beta_a = yacht.apparent_wind(u_d, v_ss, Vw, beta_w)
    hull_resistance = yacht.p.Du * u_d**2
    thrust_raw = hull_resistance - Fx
    thrust_used = max(0.0, thrust_raw)

    return {
        "solver_success": True,
        "solver_message": str(solution.message),
        "v_ss_m_s": float(v_ss),
        "rudder_angle_rad": float(delta_r_ss),
        "apparent_wind_m_s": float(Va),
        "apparent_wind_angle_rad": float(beta_a),
        "sail_Fx_N": float(Fx),
        "sail_Fy_N": float(Fy),
        "sail_yaw_moment_Nm": float(Ns),
        "hull_resistance_N": float(hull_resistance),
        "engine_thrust_raw_N": float(thrust_raw),
        "engine_thrust_used_N": float(thrust_used),
        "residual_sway": float(residual[0]),
        "residual_yaw": float(residual[1]),
    }


def plot_thrust_surface(thrust_grid, wind_speeds, wind_angles, u_d, output_path):
    wind_speed_grid, wind_angle_grid = np.meshgrid(
        wind_speeds, wind_angles, indexing="ij"
    )
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")
    surface = ax.plot_surface(
        wind_speed_grid,
        wind_angle_grid,
        thrust_grid,
        cmap="viridis",
        edgecolor="k",
    )
    ax.set_xlabel("Wind speed (m/s)")
    ax.set_ylabel("Wind velocity angle in body frame (deg)")
    ax.set_zlabel("Engine thrust used (N)")
    ax.set_title(f"Required engine thrust at prescribed surge speed {u_d:.2f} m/s")
    fig.colorbar(surface, shrink=0.6, label="Engine thrust (N)")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.show()


def main():
    # ------------------------- Case-specific inputs -------------------------
    params = YachtParameters()
    yacht = YachtModel(params)

    u_d = 7.2  # prescribed surge speed (m/s)
    vessel_heading_deg = 45.0  # propulsive vessel heading 
    Ne = 0.0  # external engine yaw moment (N m); rudder alone balances yaw

    # Technology: 1 = soft sail, 2 = rotor sail, 3 = suction sail
    sail_technology = 3
    delta_s = np.deg2rad(60.0)
    lambda1 = 2.0
    R_s = 2.0  # rotor radius (m); stored as configuration data in this model
    ks = 12.0
    sigma = 0.15

    # Sail array is a Cartesian product of x_positions and y_positions.
    # The example below therefore creates 3 x 2 = 6 sails of 150 m^2 each.
    defined_sail_area = 150.0  # m^2 per sail
    x_positions = [-70.0, -60.0, -50.0]  # m, longitudinal body coordinates
    y_positions = [-10.0, 10.0]  # m, transverse body coordinates

    # Wind grid: 13 speeds x 10 angles = 130 steady-state cases.
    wind_speeds = np.arange(0, 25, 2, dtype=float)  # 0, 2, ..., 24 m/s
    wind_angles_deg = np.arange(0, 181, 20, dtype=float)  # 0, 20, ..., 180 deg
    # ------------------------------------------------------------------------

    sails = []
    tech_params = [delta_s, lambda1, R_s, ks, sigma]
    for x in x_positions:
        for y in y_positions:
            sails.append(
                Sail(
                    area=defined_sail_area,
                    x=x,
                    y=y,
                    tech_params=tech_params,
                    technology=sail_technology,
                )
            )
    sail_array = SailArray(sails)

    output_dir = Path(__file__).resolve().parent / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "thrust_results.csv"
    plot_path = output_dir / "thrust_surface.png"

    print("WAPS steady-state thrust sweep")
    print(f"Sails: {len(sails)} | technology code: {sail_technology}")
    print(f"Prescribed surge speed: {u_d:.2f} m/s")
    print(f"Vessel heading metadata: {vessel_heading_deg:.1f} deg")
    print(
        "NOTE: beta_w is treated as a body-frame air-velocity direction (toward); "
        "vessel heading is not used to rotate it."
    )

    rows = []
    thrust_grid = np.full((len(wind_speeds), len(wind_angles_deg)), np.nan)
    for i, Vw in enumerate(wind_speeds):
        for j, beta_w_deg in enumerate(wind_angles_deg):
            beta_w = np.deg2rad(beta_w_deg)
            result = solve_one_wind_case(yacht, u_d, Vw, beta_w, sail_array, Ne)
            row = {
                "wind_speed_m_s": float(Vw),
                "beta_w_body_deg_toward": float(beta_w_deg),
                "vessel_heading_metadata_deg": float(vessel_heading_deg),
                "sail_technology_code": sail_technology,
                "n_sails": len(sails),
                "sail_area_each_m2": defined_sail_area,
                **result,
            }
            rows.append(row)

            if result["solver_success"]:
                thrust_grid[i, j] = result["engine_thrust_used_N"]
                print(
                    f"Vw={Vw:>4.1f} m/s, beta_w={beta_w_deg:>5.1f} deg | "
                    f"Fx_sail={result['sail_Fx_N']:>11.1f} N | "
                    f"Te_raw={result['engine_thrust_raw_N']:>11.1f} N | "
                    f"Te_used={result['engine_thrust_used_N']:>11.1f} N"
                )
            else:
                print(
                    f"WARNING: solver failed at Vw={Vw:.1f} m/s, "
                    f"beta_w={beta_w_deg:.1f} deg: {result['solver_message']}"
                )

    fieldnames = list(rows[0].keys()) if rows else []
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    plot_thrust_surface(thrust_grid, wind_speeds, wind_angles_deg, u_d, plot_path)
    print(f"\nCSV results saved to: {csv_path}")
    print(f"Thrust plot saved to: {plot_path}")
    print("Use engine_thrust_used_N as the non-negative thrust input for the cost model.")
    print("Check solver_success before transferring results to the costing workbook.")


if __name__ == "__main__":
    main()
