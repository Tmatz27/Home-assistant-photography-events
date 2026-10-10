# Frozen historical runtime, test-only

These files preserve accepted HA commit
`63dcc0ab46f8e2d3ad23a0ce2b1623357963430b`'s v0.16.1 implementation for
historical assertions. They are outside `custom_components` and have no import
from the installed v17 runtime. Their successful tests do **not** validate v17.

The user explicitly retired the active legacy backend, browser calculator,
notification/choice side effects, large entity attributes and v1->v2-only
migration. Keeping those behaviors as assertions against the new coordinator
would require reintroducing the rejected engine. Rather than deleting or
weakening those assertions, their implementation targets are explicitly frozen:

- The four historical HA test modules import `legacy_v16` instead of the active
  custom component; helper modules resolve to unchanged historical files in the
  integration directory through the test package's appended search path.
- `test_core_client.py` and the historical real Store test use the frozen
  scaffold via the portable `legacy_core` namespace. V17A's existing-parser
  compatibility example also targets that scaffold. The actual v17 parser is
  tested independently by `test_v17b_runtime.py`.
- Static tests of the old eight-field config form and its translations target
  the frozen form/translations. The active two-field secure form and supported
  reconfigure/reauth/Repair flows have real-HA tests.
- All 127 historical frontend tests use the unchanged v0.16.1 bundle here.
  `v17b-card.test.mjs` tests the actual new shipped bundle.

No original assertion or test method is removed. The only frozen implementation
adjustments are the appended helper search path in `__init__.py`, and registering
the old ConfigFlow under `photography_events_legacy_test` to prevent it replacing
the active flow during test discovery. The other frozen files are byte-for-byte
from the accepted baseline, including the card and calibration/eclipse data.

Independent replacement boundaries cover real private Core reads, no retired
collectors/actions, major-3 migration and registry identity, small summaries,
cache/WS/calendar privacy, truthful read-only card rendering and preserved
navigation/focus/scroll. This is an explicit retirement decision for review,
not a claim of behavioral parity.
