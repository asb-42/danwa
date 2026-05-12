# ADR-2024-05-12: PaddlePaddle Downgrade for OCR Compatibility

## Status
Accepted

## Context
The combination of PaddleOCR 3.5.0 with PaddlePaddle 3.3.1 has a critical PIR (Paddle Intermediate Representation) attribute compatibility bug with OneDNN that causes crashes during OCR operations. This affects the PP-OCRv5_server model and makes OCR functionality unusable in production deployments.

### Problem Details
- **Error**: `NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]`
- **Location**: OneDNN instruction conversion layer
- **Impact**: All CPU inference using OneDNN (default on Linux) fails
- **Affected Models**: PP-OCRv5_server, PP-OCRv5 multi-language models

### Investigation Results
- PaddlePaddle 3.3.0+ introduced PIR changes incompatible with OneDNN
- PaddleOCR 3.5.0 relies on these new PIR features
- No application-level workaround exists
- Issue is in upstream PaddlePaddle code requiring upstream fixes

## Decision
Downgrade PaddlePaddle to version 3.2.2 while maintaining PaddleOCR 3.5.0 functionality.

## Consequences

### Positive
- OCR functionality restored immediately
- Production deployments become stable
- No code changes required to existing DocumentProcessor
- Maintains all current OCR features and capabilities

### Negative
- Cannot use latest PaddlePaddle features and optimizations
- Must monitor upstream for bug fixes
- Temporary constraint on dependency versions
- May miss future PaddlePaddle improvements until fixed

### Neutral
- Requires version constraint management
- Adds compatibility check requirements
- Establishes precedent for version pinning strategy

## Implementation

### 1. Dependency Constraints
Update `pyproject.toml` to pin PaddlePaddle version:
```toml
[project.optional-dependencies]
dms = ["paddlepaddle>=3.0,<3.3.0", "paddleocr>=3.5.0"]
```

### 2. Version Compatibility Check
Add runtime version validation in DocumentProcessor:
```python
def _check_version_compatibility(self):
    import paddle
    if paddle.version.major == "3" and int(paddle.version.minor) >= 3:
        logger.warning(
            "PaddlePaddle 3.3+ has known PIR compatibility issues with OneDNN. "
            "Consider downgrading to 3.2.x for stable OCR operations."
        )
```

### 3. Documentation Updates
- Update installation instructions
- Add version compatibility matrix
- Document known issues and workarounds

### 4. Monitoring Strategy
- Track PaddlePaddle issue #77340 for resolution
- Monitor PaddlePaddle releases for OneDNN fixes
- Test new versions in staging before production

## Alternatives Considered

### 1. Disable OCR Entirely
**Pros**: Eliminates compatibility issues
**Cons**: Loses critical OCR functionality for image processing

### 2. Use Alternative OCR Engines
**Pros**: Avoids PaddlePaddle ecosystem entirely
**Cons**: Requires significant code changes, loses PaddleOCR features

### 3. GPU-Only Deployment
**Pros**: May avoid OneDNN issues
**Cons**: Increases infrastructure costs, not fully tested

### 4. Wait for Upstream Fix
**Pros**: No version constraints
**Cons**: Unknown timeline, blocks OCR functionality indefinitely

## Future Considerations

### Short-term (1-3 months)
- Monitor PaddlePaddle releases for OneDNN PIR fixes
- Test new versions in development environment
- Maintain current downgrade as stable solution

### Medium-term (3-6 months)
- Evaluate alternative OCR engines as backup
- Implement multi-engine OCR abstraction
- Consider container isolation for OCR services

### Long-term (6+ months)
- Establish comprehensive version compatibility testing
- Implement automated dependency monitoring
- Consider OCR service microservice architecture

## References
- [PaddlePaddle Issue #77340](https://github.com/PaddlePaddle/Paddle/issues/77340)
- [PaddleOCR Compatibility Report](/PADDLEOCR_COMPATIBILITY_REPORT.md)
- [DocumentProcessor Implementation](/backend/services/dms/document_processor.py)

## Implementation Status
- [x] ADR created and approved
- [ ] pyproject.toml updated
- [ ] Version compatibility check implemented
- [ ] Documentation updated
- [ ] Testing completed

---

**Decision Date**: 2024-05-12  
**Decision Maker**: Development Team  
**Review Date**: 2024-08-12 (3 months)  
**Status**: Active
