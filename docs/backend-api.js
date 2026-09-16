(() => {
  "use strict";

  const configuredUrl = document
    .querySelector(
      'meta[name="bibtex-verifier-api"]'
    )
    ?.getAttribute("content")
    ?.trim();

    const isLocalHost =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1";

  const defaultUrl =
    isLocalHost && window.location.port !== "8000"
      ? "http://127.0.0.1:8000"
      : window.location.origin;

  const apiBaseUrl = (
    configuredUrl || defaultUrl
  ).replace(/\/+$/, "");

  class BackendError extends Error {
    constructor(message, status = null) {
      super(message);
      this.name = "BackendError";
      this.status = status;
    }
  }

  async function verifyBibtex(bibtex) {
    const controller = new AbortController();

    const timeout = window.setTimeout(
      () => controller.abort(),
      120000,
    );

    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/verify`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ bibtex }),
          signal: controller.signal,
        },
      );

      if (!response.ok) {
        let message =
          `Verification failed with HTTP ${response.status}`;

        try {
          const payload = await response.json();

          if (payload.detail) {
            message = payload.detail;
          }
        } catch {
          // Keep the HTTP status when
          // the response is not JSON.
        }

        throw new BackendError(
          message,
          response.status,
        );
      }

      return await response.json();
    } catch (error) {
      if (error.name === "AbortError") {
        throw new BackendError(
          "The verification request timed out.",
        );
      }

      if (error instanceof BackendError) {
        throw error;
      }

      throw new BackendError(
        "The Python verification service is unavailable. "
          + "Make sure it is running on "
          + `${apiBaseUrl}.`,
      );
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function resultToFound(result) {
    if (!result?.matched) {
      return null;
    }

    const sources = Array.isArray(
      result.sources
    )
      ? result.sources
      : [];

    return {
      ...result.matched,
      _source: sources.join("+"),
      _sourceCount: sources.length,
      _confidence: result.confidence,
      _evidence: result.evidence,
      _backendStatus: result.status,
    };
  }

  window.BibBackend = Object.freeze({
    BackendError,
    apiBaseUrl,
    resultToFound,
    verifyBibtex,
  });
})();