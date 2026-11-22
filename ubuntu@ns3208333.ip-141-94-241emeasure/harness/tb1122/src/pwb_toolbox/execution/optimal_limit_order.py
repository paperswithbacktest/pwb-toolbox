import math

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import odeint


def optimal_limit_order_formula(q_max, t_max, mu, sigma, A, k, gamma, b, is_plot=False):
    """
    q_max : Quantity in ATS to execute
    t_max : Time in seconds remaining to execute
    mu : Trend in tick per second
    sigma : Volatility in tick per second squared
    A : arrival rate at best quote
    k : exponential decreasing parameter of arrival rate
    gamma : absolute risk aversion
    b : cost per share to liquidate the remaining position in ticks
    """

    alpha = k / 2 * gamma * np.power(sigma, 2)
    beta = k * mu
    eta = A * np.power(1 + gamma / k, -(1 + k / gamma))
    w_0 = 1

    def w_T(q):
        return np.exp(-k * q * b)

    def linear_ode(w_q, w_q_1, q):
        return (alpha * np.power(q, 2) - beta * q) * w_q - eta * w_q_1

    def linear_ode_system(y, t):
        w = [w_0, *y]
        dydt = [linear_ode(w[q], w[q - 1], q) for q in range(1, q_max + 1)]
        return dydt

    w_T = [w_T(q) for q in range(1, q_max + 1)]
    t = np.linspace(0, -t_max, 100)

    w = odeint(linear_ode_system, w_T, t, args=())

    delta = {}
    for q in range(1, q_max + 1):
        if q == 1:
            delta[q] = 1 / k * np.log(w[:, q - 1] / w_0) + 1 / gamma * np.log(
                1 + gamma / k
            )
        else:
            delta[q] = 1 / k * np.log(w[:, q - 1] / w[:, q - 2]) + 1 / gamma * np.log(
                1 + gamma / k
            )

    if is_plot:
        for q in range(1, q_max + 1):
            plt.plot(t, delta[q], "b", label=f"delta_{q}(t)")
        plt.legend(loc="best")
        plt.xlabel("t")
        plt.ylabel("Ask price - Limit order price")
        plt.grid()
        plt.show()

    return delta[q_max][-1]


def get_optimal_quote(symbol, quantity, time_in_seconds, is_plot=False):
    if symbol == "demo" or True:
        parameters = {
            "mu": 0.01,  # Drift term
            "sigma": 0.3,  # Volatility
            "A": 0.1,  # Arrival rate of market orders
            "k": 0.3,  # Liquidity impact parameter
            "b": 3,  # Liquidation cost
            "tick_size": 0.01,  # Tick size
            "average_trading_size": 100,  # Average trading size
        }

    gamma = 5e-4 / parameters["tick_size"]
    quote = optimal_limit_order_formula(
        q_max=math.ceil(quantity / parameters["average_trading_size"]),
        t_max=time_in_seconds,
        mu=0,
        sigma=parameters["sigma"],
        A=parameters["A"],
        k=parameters["k"],
        gamma=gamma,
        b=parameters["b"],
        is_plot=is_plot,
    )
    quote = quote * parameters["tick_size"]
    if not math.isfinite(quote):
        return 0.0
    return quote


if __name__ == "__main__":
    symbol = "demo"
    quantity = 500
    time_in_seconds = 600
    quote = get_optimal_quote(
        symbol=symbol, quantity=quantity, time_in_seconds=time_in_seconds
    )
    buy_sign = "-" if np.sign(-1 * quote) < 0 else "+"
    sell_sign = "-" if np.sign(quote) < 0 else "+"
    print(f"buy@mid {buy_sign} {np.abs(quote)} USD")
    print(f"sell@mid {sell_sign} {np.abs(quote)} USD")
