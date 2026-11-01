import unittest

import google_winner_pack as gwp
import report_quality as rq
import winner_pack as wp


def ad(aid, asset, video=True, page='p'):
    return dict(ad_archive_id=aid, asset_id=asset, collation_id=aid, page_id=page,
                page_name=page, body='{{product.brand}}', title='', video_urls=['video'] if video else [],
                days_running=30, start_ts=1, collation_count=999)


class EvidenceRegressionTests(unittest.TestCase):
    def tearDown(self):
        rq.set_reference(None)

    def test_dco_placeholder_does_not_combine_distinct_visuals(self):
        groups = wp.group_creatives([ad('1', 'a'), ad('2', 'b')])
        self.assertEqual(len(groups), 2)
        self.assertEqual([g['copies'] for g in groups], [1, 1])

    def test_same_design_splits_video_and_still_but_keeps_video_captions(self):
        rows = [ad('1', 'a'), ad('2', 'a'), ad('3', 'a', False)]
        rows[1]['body'] = 'A different caption'
        groups = wp.group_creatives(rows)
        video = next(g for g in groups if g['is_video'])
        self.assertEqual({r['ad_archive_id'] for r in video['ads']}, {'1', '2'})
        self.assertEqual(video['copies'], 2)  # not the upstream aggregate of 999
        self.assertEqual(len(groups), 2)

    def test_missing_visual_id_does_not_fall_back_to_caption(self):
        rows = [ad('1', None), ad('2', None)]
        self.assertEqual(len(wp.group_creatives(rows)), 2)

    def test_dco_without_video_url_is_not_assumed_to_be_image(self):
        row = ad('1', 'a', False)
        row['display_format'] = 'DCO'
        groups = wp.group_creatives([row])
        self.assertFalse(groups[0]['is_video'])
        self.assertFalse(groups[0]['is_image'])
        self.assertEqual(wp.pick(groups, 12, 3, False), [])

    def test_shared_youtube_video_does_not_mix_companies(self):
        rows = [dict(youtube_id='shared', competitor=name, days_shown=30, last_ts=100,
                     first_ts=1, first_shown='2026-01-01', last_shown='2026-01-30',
                     creative_id=str(i), platforms='YouTube') for i, name in enumerate(['A', 'B'])]
        groups = gwp.group_videos(rows, None)
        self.assertEqual(len(groups), 2)
        self.assertEqual({v['copies'] for v in groups}, {1})

    def test_coverage_distinguishes_missing_ids_and_recent_video(self):
        rows = [dict(format='Video', active=True, youtube_id=''),
                dict(format='Video', active=False, youtube_id='id'),
                dict(format='Ảnh', active=True, youtube_id='')]
        self.assertEqual(rq.coverage(rows, 'google'), dict(videos=2, unresolved=1, active_videos=1, active_unresolved=1))

    def test_reference_clock_and_empty_coverage(self):
        rq.set_reference('2026-10-29T14:29:00+07:00')
        self.assertEqual(rq.today().isoformat(), '2026-10-29')
        self.assertEqual(rq.stamp(), '29/10/2026 14:29')
        self.assertEqual(rq.coverage([], 'google')['videos'], 0)
        self.assertIn('0/0', rq.coverage_box([], 'google'))


if __name__ == '__main__':
    unittest.main()
