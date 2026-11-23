#!/usr/bin/env python3
"""KOTHA R1 common statistical interface.

One engine is used by the empirical analyses and the simulation.

Model (normal-normal random effects on log effect estimates y_i with SE s_i):
    y_i | theta_i ~ N(theta_i, s_i^2),  theta_i ~ N(mu, tau^2),  tau ~ HalfNormal(tau_scale)
Target parameter: mu (mean log effect in the population represented by the RCTs), with a
prior on mu that encodes external evidence (or is vague). Conditional on tau the posterior of
mu is conjugate; tau is integrated by quadrature on a grid. Every prior on mu is a finite
mixture of normals, so posteriors are exact Gaussian mixtures over (tau grid x components).

Borrowing priors on mu (external summary m_E, V_E = Var(mu_E), T2_E = E[tau_E^2]):
  * vague                    N(0, 10^2)                                  (RCT-only)
  * fixed-alpha power prior  N(m_E, V_E / alpha)   (summary-level; alpha fixed, so the
                             normalising constant does not depend on data and is irrelevant)
  * normalised power prior   alpha ~ U(0,1); prior N(m_E, V_E / alpha) normalised for each
                             alpha (Duan et al. 2006; Neuenschwander et al. 2009) -> mixture
  * robust MAP               (1-w) N(m_E, V_E + T2_E) + w N(m_E, 2^2)  (Schmidli et al. 2014)
  * study-level shared-tau power prior (legacy Module T formulation, for validation only)
"""
import numpy as np
from scipy import stats
from scipy.special import ndtr, logsumexp

VAGUE_SD = 10.0
UNIT_INFO_SD = 2.0          # unit-information SD for a log hazard/odds ratio (~one event)
Z975 = stats.norm.ppf(0.975)


def tau_grid(scale=0.5, n=401, upper=None, kind='halfnormal'):
    upper = upper if upper is not None else (4 * scale if kind == 'halfnormal' else 5.0)
    t = np.linspace(0.0, upper, n)
    if kind == 'halfnormal':
        lp = stats.halfnorm.logpdf(t, scale=scale)
    elif kind == 'halfcauchy':
        lp = stats.halfcauchy.logpdf(t, scale=scale)
    elif kind == 'zero':
        return np.array([0.0]), np.array([0.0])
    else:
        raise ValueError(kind)
    w = np.full(n, t[1] - t[0]); w[0] /= 2; w[-1] /= 2
    return t, lp + np.log(w)


def _rct_terms(y, s, tau):
    """Per tau: precision P, mean ybar and log K with prod N(y_i; mu, v_i) = K * N(mu; ybar, 1/P)."""
    y = np.asarray(y, float)[None, :]; s = np.asarray(s, float)[None, :]
    v = s ** 2 + tau[:, None] ** 2
    P = np.sum(1 / v, axis=1)
    ybar = np.sum(y / v, axis=1) / P
    logK = np.sum(stats.norm.logpdf(y, ybar[:, None], np.sqrt(v)), axis=1) + 0.5 * np.log(2 * np.pi / P)
    return P, ybar, logK


class Mixture:
    def __init__(self, logw, mean, var):
        logw = np.ravel(logw); self.mean = np.ravel(mean); self.var = np.ravel(var)
        self.w = np.exp(logw - logsumexp(logw))
        self.sd = np.sqrt(self.var)

    def cdf(self, x):
        x = np.atleast_1d(x)
        return np.sum(self.w[None, :] * ndtr((x[:, None] - self.mean[None, :]) / self.sd[None, :]), axis=1)

    def moments(self):
        m = np.sum(self.w * self.mean)
        v = np.sum(self.w * (self.var + self.mean ** 2)) - m ** 2
        return m, v

    def quantile(self, q, iters=60):
        q = np.atleast_1d(q).astype(float)
        m, v = self.moments(); sd = np.sqrt(v)
        lo = np.full(q.shape, np.min(self.mean - 12 * self.sd)); hi = np.full(q.shape, np.max(self.mean + 12 * self.sd))
        for _ in range(iters):
            mid = (lo + hi) / 2
            c = self.cdf(mid)
            lo = np.where(c < q, mid, lo); hi = np.where(c >= q, mid, hi)
        return (lo + hi) / 2


def posterior_mu(y, s, prior_components, tau=None, logtau=None, tau_prior=('halfnormal', 0.5)):
    """prior_components: list of (logw, m, V) scalars or arrays over the tau grid."""
    if tau is None:
        tau, logtau = tau_grid(kind=tau_prior[0], scale=tau_prior[1])
    P, ybar, logK = _rct_terms(y, s, tau)
    LW, M, V, TAU = [], [], [], []
    for (lw, m, Vk) in prior_components:
        lw = np.broadcast_to(lw, tau.shape); m = np.broadcast_to(m, tau.shape); Vk = np.broadcast_to(Vk, tau.shape)
        logmarg = logK + stats.norm.logpdf(ybar, m, np.sqrt(1 / P + Vk))
        pv = 1 / (P + 1 / Vk)
        pm = pv * (ybar * P + m / Vk)
        LW.append(logtau + lw + logmarg); M.append(pm); V.append(pv)
    LW = np.stack(LW, 1); M = np.stack(M, 1); V = np.stack(V, 1)
    mix = Mixture(LW, M, V)
    comp_w = np.exp(logsumexp(LW, axis=0) - logsumexp(LW))      # posterior weight per prior component
    tau_w = np.exp(logsumexp(LW, axis=1) - logsumexp(LW))
    return mix, comp_w, tau, tau_w


def summarise(mix, thresholds=(0.0, np.log(0.9), np.log(0.85), np.log(0.8)), level=0.95):
    m, v = mix.moments()
    lo, med, hi = mix.quantile([(1 - level) / 2, 0.5, 1 - (1 - level) / 2])
    out = {'mean': m, 'sd': np.sqrt(v), 'median': med, 'lo': lo, 'hi': hi}
    for t in thresholds:
        out[f'p_lt_{np.exp(t):.2f}'] = float(mix.cdf(t)[0])
    return out


# ---------- external-evidence summary ----------
def external_summary(yE, sE, tau_prior=('halfnormal', 0.5)):
    mix, _, tau, tau_w = posterior_mu(yE, sE, [(0.0, 0.0, VAGUE_SD ** 2)], tau_prior=tau_prior)
    m, v = mix.moments()
    return {'m_E': m, 'V_E': v, 'T2_E': float(np.sum(tau_w * tau ** 2)), 'k_E': len(yE)}


# ---------- methods ----------
def rct_only(yR, sR, **kw):
    return posterior_mu(yR, sR, [(0.0, 0.0, VAGUE_SD ** 2)], **kw)


def fixed_power_prior(yR, sR, ext, alpha, **kw):
    if alpha <= 0:
        return rct_only(yR, sR, **kw)
    return posterior_mu(yR, sR, [(0.0, ext['m_E'], ext['V_E'] / alpha)], **kw)


def normalised_power_prior(yR, sR, ext, alphas=None, **kw):
    alphas = np.linspace(0.01, 1.0, 100) if alphas is None else alphas
    lw0 = -np.log(len(alphas))
    comps = [(lw0, ext['m_E'], ext['V_E'] / a) for a in alphas]
    mix, cw, tau, tw = posterior_mu(yR, sR, comps, **kw)
    return mix, cw, alphas


def robust_map(yR, sR, ext, w_vague=0.5, vague_sd=UNIT_INFO_SD, **kw):
    comps = [(np.log(1 - w_vague), ext['m_E'], ext['V_E'] + ext['T2_E']),
             (np.log(w_vague), ext['m_E'], vague_sd ** 2)]
    return posterior_mu(yR, sR, comps, **kw)


def study_level_power_prior(yR, sR, yE, sE, alpha, tau_prior=('halfcauchy', 0.5), mu_prior_sd=VAGUE_SD):
    """Legacy Module T: L_R(mu,tau) * L_E(mu,tau)^alpha * p(mu) p(tau); exact by quadrature."""
    tau, logtau = tau_grid(kind=tau_prior[0], scale=tau_prior[1], n=2001, upper=20.0)
    if alpha <= 0:
        return posterior_mu(yR, sR, [(0.0, 0.0, mu_prior_sd ** 2)], tau=tau, logtau=logtau)
    PE, ybE, logKE = _rct_terms(yE, sE, tau)
    # [K_E N(mu; ybE, 1/PE)]^alpha = exp(c) * N(mu; ybE, 1/(alpha PE))
    c = alpha * logKE + alpha * 0.5 * np.log(PE / (2 * np.pi)) + 0.5 * np.log(2 * np.pi / (alpha * PE))
    # combine with vague N(0, sd^2) prior on mu: product of two normals in mu
    V1 = 1 / (alpha * PE); V0 = mu_prior_sd ** 2
    Vc = 1 / (1 / V1 + 1 / V0); mc = Vc * (ybE / V1)
    c = c + stats.norm.logpdf(ybE, 0.0, np.sqrt(V1 + V0))
    return posterior_mu(yR, sR, [(c, mc, Vc)], tau=tau, logtau=logtau)


# ---------- frequentist ----------
def fixed_effect(y, s):
    w = 1 / np.asarray(s) ** 2
    est = np.sum(w * y) / np.sum(w); se = 1 / np.sqrt(np.sum(w))
    z = est / se
    return {'est': est, 'se': se, 'lo': est - Z975 * se, 'hi': est + Z975 * se, 'z': z, 'p': 2 * stats.norm.sf(abs(z))}


def dersimonian_laird(y, s):
    y = np.asarray(y, float); s = np.asarray(s, float)
    w = 1 / s ** 2; k = len(y)
    fe = np.sum(w * y) / np.sum(w)
    Q = float(np.sum(w * (y - fe) ** 2))
    C = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    tau2 = max(0.0, (Q - (k - 1)) / C) if k > 1 else 0.0
    wr = 1 / (s ** 2 + tau2)
    est = np.sum(wr * y) / np.sum(wr); se = 1 / np.sqrt(np.sum(wr))
    z = est / se
    I2 = max(0.0, (Q - (k - 1)) / Q) * 100 if Q > 0 else 0.0
    return {'est': est, 'se': se, 'lo': est - Z975 * se, 'hi': est + Z975 * se, 'z': z,
            'p': 2 * stats.norm.sf(abs(z)), 'tau2': tau2, 'Q': Q, 'Q_p': stats.chi2.sf(Q, k - 1) if k > 1 else np.nan, 'I2': I2, 'k': k}


# ---------- KOTHA workflow components ----------
def required_information(mcid_ratio, alpha=0.05, power=0.80):
    """Fisher information (1/SE^2 of the log effect) needed to detect log(mcid) with given power."""
    return ((stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)) / abs(np.log(mcid_ratio))) ** 2


def ois_events(mcid_ratio, alpha=0.05, power=0.80, D2=0.0):
    """Events required (Schoenfeld / log-OR rare-event approximation, 1:1), heterogeneity-adjusted by 1/(1-D2)."""
    return 4 * (stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)) ** 2 / np.log(mcid_ratio) ** 2 / (1 - D2)


def compatibility(rct_mean, rct_var, ext):
    """Prior-predictive conflict z for the RCT-population mean vs the MAP predictive of external evidence."""
    z = (rct_mean - ext['m_E']) / np.sqrt(rct_var + ext['V_E'] + ext['T2_E'])
    return {'z': z, 'p': 2 * stats.norm.sf(abs(z))}


def kotha_decision(info_fraction, relevance_adequate, compat_p, conflict_level=0.05):
    """Prespecified KOTHA R1 rule (see simulation_protocol_R1.md / BORROWING_METHOD_SELECTION).

    Stage B states are diagnostic; borrowing is considered only if the RCT evidence is either
    informationally insufficient or of inadequate relevance, AND no statistical conflict is detected.
    """
    info_ok = info_fraction >= 1.0
    if info_ok and relevance_adequate:
        return 'B1: adequate information and relevance -> RCT-only', False
    if compat_p < conflict_level:
        return ('B2/B3/B4 with prior-data conflict -> RCT-only; external evidence incompatible', False)
    state = {(True, False): 'B2: adequate information, inadequate relevance',
             (False, True): 'B3: inadequate information, adequate relevance',
             (False, False): 'B4: inadequate information and relevance'}[(info_ok, relevance_adequate)]
    return state + ' -> borrow (robust MAP)', True
