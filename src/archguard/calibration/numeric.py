"""Small deterministic weighted linear solvers; fitting never serializes estimators."""

import math

from archguard.architecture.hybrid.calibration import StructuralCalibrationError, stable_sigmoid


def solve(matrix: list[list[float]], rhs: list[float]) -> tuple[float, ...]:
    n = len(rhs)
    a = [row[:] + [value] for row, value in zip(matrix, rhs, strict=True)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(a[row][col]))
        if abs(a[pivot][col]) < 1e-14:
            raise StructuralCalibrationError("singular fitting system")
        a[col], a[pivot] = a[pivot], a[col]
        divisor = a[col][col]
        a[col] = [value / divisor for value in a[col]]
        for row in range(n):
            if row != col:
                factor = a[row][col]
                a[row] = [x - factor * y for x, y in zip(a[row], a[col], strict=True)]
    result = tuple(row[-1] for row in a)
    if any(not math.isfinite(x) for x in result):
        raise StructuralCalibrationError("nonfinite fitting result")
    return result


def fit_coefficients(
    x: tuple[tuple[float, ...], ...],
    y: tuple[int, ...],
    weights: tuple[float, ...],
    regularization: float,
    *,
    logistic: bool,
    max_iterations: int = 200,
    tolerance: float = 1e-10,
) -> tuple[tuple[float, ...], float, int]:
    if (
        not x
        or len(x) != len(y)
        or len(y) != len(weights)
        or any(len(row) != len(x[0]) for row in x)
        or set(y) != {0, 1}
        or min(weights) <= 0
        or regularization <= 0
        or any(not math.isfinite(v) for row in x for v in row)
    ):
        raise StructuralCalibrationError("invalid fitting matrix/labels/weights")
    design = tuple((1.0, *row) for row in x)
    n = len(design[0])

    def penalty(index: int) -> float:
        return regularization if index else 0.0

    if not logistic:
        h = [
            [
                math.fsum(w * row[i] * row[j] for row, w in zip(design, weights, strict=True))
                + (penalty(i) if i == j else 0)
                for j in range(n)
            ]
            for i in range(n)
        ]
        rhs = [
            math.fsum(w * label * row[i] for row, label, w in zip(design, y, weights, strict=True))
            for i in range(n)
        ]
        beta = solve(h, rhs)
        return beta[1:], beta[0], 1

    def loss(beta: tuple[float, ...]) -> float:
        result = []
        for row, label, w in zip(design, y, weights, strict=True):
            z = math.fsum(a * b for a, b in zip(row, beta, strict=True))
            result.append(w * (max(z, 0) + math.log1p(math.exp(-abs(z))) - label * z))
        return math.fsum(result) + regularization * math.fsum(b * b for b in beta[1:]) / 2

    beta = (0.0,) * n
    for iteration in range(1, max_iterations + 1):
        p = tuple(
            stable_sigmoid(math.fsum(a * b for a, b in zip(row, beta, strict=True)))
            for row in design
        )
        gradient = [
            math.fsum(
                w * (probability - label) * row[i]
                for row, label, w, probability in zip(design, y, weights, p, strict=True)
            )
            + penalty(i) * beta[i]
            for i in range(n)
        ]
        if max(abs(g) for g in gradient) <= tolerance:
            return beta[1:], beta[0], iteration
        h = [
            [
                math.fsum(
                    w * probability * (1 - probability) * row[i] * row[j]
                    for row, w, probability in zip(design, weights, p, strict=True)
                )
                + (penalty(i) if i == j else 0)
                for j in range(n)
            ]
            for i in range(n)
        ]
        step = solve(h, gradient)
        old_loss = loss(beta)
        scale = 1.0
        for _ in range(40):
            proposed = tuple(b - scale * d for b, d in zip(beta, step, strict=True))
            if loss(proposed) <= old_loss + 1e-14:
                beta = proposed
                break
            scale /= 2
        else:
            raise StructuralCalibrationError("logistic line search did not converge")
    raise StructuralCalibrationError("logistic candidate did not converge")
