"""Non-identifiable probabilistic integrity test for the flight/landing mechanism."""
import unittest
import numpy as np
from scipy.linalg import svd

class SyntheticCubeFlight(unittest.TestCase):
    def test_selection_probabilities_and_group_quotas(self):
        rng=np.random.default_rng(1777)
        blocks=np.array([0]*10+[1]*14)
        targets=(3,5)
        pi=np.where(blocks==0,3/10,5/14)
        X=np.array([(blocks==0).astype(float),(blocks==1).astype(float),
                    (np.arange(24)%3==0).astype(float),(np.arange(24)%5<2).astype(float)])
        A=X/pi
        def move(p,idx,v):
            pos=v>1e-12;neg=v<-1e-12
            plus=[];minus=[]
            if pos.any():
                plus.extend(((1-p[idx[pos]])/v[pos]).tolist())
                minus.extend((p[idx[pos]]/v[pos]).tolist())
            if neg.any():
                plus.extend((p[idx[neg]]/(-v[neg])).tolist())
                minus.extend(((1-p[idx[neg]])/(-v[neg])).tolist())
            up=min(plus);dn=min(minus)
            if rng.random()<dn/(up+dn):p[idx]+=up*v
            else:p[idx]-=dn*v
            p[idx]=np.clip(p[idx],0,1)
        def draw():
            p=pi.copy();q=A.shape[0]
            while True:
                idx=np.flatnonzero((p>1e-10)&(p<1-1e-10))
                if len(idx)<=q:break
                u=rng.choice(idx,q+1,replace=False)
                v=svd(A[:,u],full_matrices=True,lapack_driver='gesvd',check_finite=False)[2][-1]
                v=v/max(abs(v));move(p,u,v)
            for h in (0,1):
                ii=np.where(blocks==h)[0]
                while True:
                    active=ii[(p[ii]>1e-10)&(p[ii]<1-1e-10)]
                    if len(active)<2:break
                    ij=rng.choice(active,2,replace=False);move(p,ij,np.array([1.,-1.]))
            z=np.rint(p).astype(int)
            self.assertEqual(int(z.sum()),8)
            self.assertEqual(int(z[blocks==0].sum()),3)
            self.assertEqual(int(z[blocks==1].sum()),5)
            return z
        trials=np.asarray([draw() for _ in range(400)])
        self.assertLess(float(np.max(np.abs(trials.mean(axis=0)-pi))),0.09)

if __name__=='__main__':unittest.main()
