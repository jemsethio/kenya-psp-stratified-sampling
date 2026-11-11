"""Fast tests that require no identifiable participant data or artifact_tool."""
import unittest
import math
import numpy as np


def largest_remainder(group_counts,target):
    total=sum(group_counts)
    floors=[math.floor(target*v/total) for v in group_counts]
    order=sorted(range(len(group_counts)),key=lambda j:(-(target*group_counts[j]/total-floors[j]),j))
    for j in order[:target-sum(floors)]:floors[j]+=1
    return floors

class TestCoreDesign(unittest.TestCase):
    def test_county_targets(self):
        self.assertEqual(157+158,315)
        self.assertEqual(2*(157+158),630)
    def test_apportionment(self):
        n=[15,10,25,50];a=largest_remainder(n,30)
        self.assertEqual(sum(a),30);self.assertEqual(a,[5,3,7,15])
    def test_probabilities(self):
        for N,n in [(100,30),(16,4),(41,11)]:
            p=np.repeat(n/N,N)
            self.assertAlmostEqual(float(p.sum()),n)
            self.assertTrue(np.all((p>0)&(p<1)))
    def test_study_buffer(self):
        self.assertEqual(math.ceil(267/0.85),315)
    def test_swap_invariance_of_squared_differences(self):
        a,b=20,24
        self.assertEqual((a-b)**2,(b-a)**2)

if __name__=='__main__':unittest.main()
