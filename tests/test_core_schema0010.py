"""Accepted 0010 wire compatibility never grants new presentation authority."""
import copy
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

import test_integration
test_integration._load_package()
from photography_events.core_client import PhotographyEventsCoreClient, CoreAssessment, CoreProtocolError, CoreVersionError
from photography_events.core_bridge import CoreBridge
from photography_events.projection import DestinationPolicy, InvalidProjection, SUPPORTED_CORE_SCHEMAS, canonical_digest, sanitize_envelope, validate_envelope
from test_core_client import Session, Response
from v17b_fixtures import NOW, payload, policy_documents

CAPTURE=json.loads((Path(__file__).parent/'fixtures/core-schema0010.json').read_text(encoding='utf-8'))
RESPONSES=CAPTURE['responses']


class CoreSchema0010Tests(unittest.IsolatedAsyncioTestCase):
    def client(self,*values):
        session=Session(*(Response(v) for v in values))
        return PhotographyEventsCoreClient(session,'http://core.invalid','PRIVATE_TOKEN'),session

    async def test_accepted_route_capture_crosses_all_transport_and_projection_boundaries(self):
        self.assertEqual(SUPPORTED_CORE_SCHEMAS,('0008','0009','0010'))
        self.assertEqual(CAPTURE['provenance']['commit'],'10bde5f0dcb57821f36a971af9e3dc4183271202')
        client,session=self.client(*(RESPONSES[k] for k in ('health','opportunities','sources')))
        self.assertEqual((await client.health()).schema_version,'0010')
        result=await client.opportunities()
        self.assertEqual(result.payload['schema_version'],'0010')
        self.assertEqual(len((await client.source_health())['items']),2)
        safe=sanitize_envelope(result.payload,DestinationPolicy.load())
        self.assertEqual(safe['items'][0]['location']['policy'],'withheld')
        self.assertFalse(safe['items'][0]['eligibility'])
        self.assertNotIn('PRIVATE_TOKEN',json.dumps(safe)+repr(result))
        self.assertTrue(all(not options['allow_redirects'] for _,options in session.requests))
        for key,state in (('empty','complete'),('incomplete','incomplete')):
            parsed=CoreAssessment.parse(RESPONSES[key])
            self.assertEqual(parsed.payload['assessment_state'],state)
            self.assertEqual(parsed.items,())

    async def test_new_schema_rejects_debug_bad_rows_and_unreviewed_identities(self):
        for change in (lambda x:x.update(mode='shadow'),lambda x:x.update(preview_opportunities=[]),
            lambda x:x['items'][0].update(phenomenon_key='wildflower_bloom'),
            lambda x:x['items'][0].update(occurrence_key='station-or-observer-id'),
            lambda x:x['items'][0].update(eligibility='true'),
            lambda x:x['items'][0].update(valid_until='invalid')):
            data=copy.deepcopy(RESPONSES['opportunities']);change(data)
            with self.assertRaises(CoreProtocolError):CoreAssessment.parse(data)
        for schema in ('0011','9999','0010 ',10,True,None,[],{}):
            for key,method in (('health','health'),('opportunities','opportunities'),('sources','source_health')):
                with self.subTest(schema=schema,endpoint=key):
                    data={**RESPONSES[key],'schema_version':schema}
                    client,_=self.client(data)
                    with self.assertRaises(CoreVersionError):await getattr(client,method)()
            with self.assertRaises(InvalidProjection):
                validate_envelope({**RESPONSES['opportunities'],'schema_version':schema})

    async def test_0008_0009_0010_refresh_and_cache_preserve_clocks_then_reject_future(self):
        values=[]
        for schema in ('0008','0009','0010'):
            values.extend(({**RESPONSES['health'],'schema_version':schema},
                {**payload(),'schema_version':schema},
                {**RESPONSES['sources'],'schema_version':schema,'generated_at':NOW.isoformat()}))
        client,_=self.client(*values)
        store=SimpleNamespace(async_save=AsyncMock())
        bridge=CoreBridge(client,store,lambda:NOW,namespace='same-origin-and-principal')
        for schema in ('0008','0009','0010'):
            await bridge.refresh()
            self.assertEqual(bridge.availability,'online')
            self.assertEqual(bridge.payload['schema_version'],schema)
            self.assertFalse(bridge.view()['notifications_enabled'])
        saved=store.async_save.call_args.args[0]
        self.assertEqual(saved['payload']['data_as_of'],payload()['data_as_of'])
        self.assertEqual(saved['fetched_at'],NOW.isoformat())
        restarted=CoreBridge(client,SimpleNamespace(async_load=AsyncMock(return_value=saved)),
            lambda:NOW+timedelta(minutes=5),namespace='same-origin-and-principal')
        await restarted.initialize()
        self.assertEqual(restarted.cached['schema_version'],'0010')
        self.assertEqual(restarted.cached_fetch,NOW)
        restarted.client,_=self.client({**RESPONSES['health'],'schema_version':'0011'})
        await restarted.refresh()
        self.assertEqual(restarted.availability,'incompatible')
        self.assertIsNone(restarted.payload)
        self.assertIsNone(restarted.cached)

    async def test_0010_does_not_widen_destination_artifact_or_source_disclosure(self):
        artifact,review=policy_documents()
        self.assertEqual(DestinationPolicy(artifact,review).state,'verified')
        artifact['schema_version']='0010'
        review['content_sha256']=canonical_digest(artifact)
        self.assertEqual(DestinationPolicy(artifact,review).state,'unverified')
        source=copy.deepcopy(RESPONSES['sources'])
        source['items'][0].update(key='cdec_snow',error_code='native-private-diagnostic')
        client,_=self.client(source)
        result=await client.source_health()
        self.assertEqual(result['items'][0]['key'],'core')
        self.assertEqual(result['items'][0]['error_code'],'source_unavailable')
        self.assertNotIn('native-private-diagnostic',json.dumps(result))
        source['items'][0]['state']='invented'
        client,_=self.client(source)
        with self.assertRaises(CoreProtocolError):await client.source_health()
