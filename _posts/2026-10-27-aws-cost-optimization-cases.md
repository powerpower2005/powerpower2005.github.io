---
title: AWS 비용이 증가하는 운영 케이스와 설계 대응
date: 2026-10-27 00:00:00 +0900
description: NAT 경로, 저사용량 Endpoint, 멀티클라우드 DB 통신, Kubernetes Requests, Spot 운영에서 비용 원인과 권장 대응 비교
tags: [AWS, DevOps, 비용최적화, Kubernetes, 멀티클라우드, 협찬]
---

> 출판사에서 도서를 제공받았음.

『요즘 개발자를 위한 AWS 비용 최적화』를 읽고, 운영에서 비용이 커지는 케이스를 중심으로 정리함. 최적화의 기준은 **성능·보안·가용성 요구사항을 충족하면서 요청당 비용을 낮추는 것**임. AWS Well-Architected의 비용 최적화와 신뢰성을 함께 고려한 대응 방향임.

## NAT Gateway의 Cross-AZ와 S3 경유

**케이스:** AZ-A의 애플리케이션이 AZ-B의 NAT Gateway를 이용하거나, 대용량 S3 업로드·다운로드를 NAT로 처리하는 구성임.

| 비용 발생 원인 | 권장 대응 |
|---|---|
| NAT 시간당 요금과 GB당 처리비에 Cross-AZ 전송비가 추가될 수 있음 | AZ별 NAT와 동일 AZ 라우팅 검토. 추가 NAT 고정비와 절감되는 전송비 비교 필요 |
| 같은 리전의 S3 통신까지 NAT 처리비 발생 | S3 Gateway Endpoint 적용과 해당 서브넷의 라우팅·Endpoint Policy·버킷 정책 검증 권장 |

Gateway Endpoint 자체는 시간당·데이터 처리 요금이 없으나 S3 요청·저장 비용은 별도임. 단일 AZ NAT 공유는 고정비 절감과 함께 해당 AZ 장애 시 외부 통신 중단 위험을 동반함. 운영 환경의 AZ 장애 요구사항을 먼저 결정할 필요가 있음. [NAT 과금 및 권장 구성](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-pricing.html), [S3 Gateway Endpoint](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html) 참조.

## 사용량이 적은 Interface Endpoint

**케이스:** 호출이 적은 STS·Secrets Manager 등에 Interface Endpoint를 서비스별·AZ별로 생성한 구성임.

**비용 원인:** 트래픽이 없어도 Endpoint의 AZ별 시간당 요금 발생. NAT를 계속 유지하는 경우 Endpoint 추가만으로 NAT 고정비가 줄어들지는 않음.

**권장 대응:** 서비스별 전송량과 보안상 사설 접근 필요성 확인 후 적용 범위 결정. 기존 NAT를 유지하고 전송비 차이를 제외한 단순 비교식은 다음과 같음.

```text
월 절감액
= 전환 트래픽 GB × (NAT GB당 처리 단가 − Endpoint GB당 처리 단가)
  − Endpoint의 서비스 수 × AZ 수 × 월 운영시간 × 시간당 단가
```

Cross-AZ·VPC 연결비 등 경로 차이는 별도 반영 필요. Endpoint 중앙화 시에도 연결 처리비·DNS 운영·장애 영향 범위까지 합산 필요. 비용을 이유로 필수 사설 접근 요건을 해제하는 방식은 지양함. [AWS PrivateLink 요금](https://aws.amazon.com/privatelink/pricing/) 참조.

## AWS RDS와 GCP 애플리케이션 간 통신

**케이스:** GKE의 애플리케이션이 AWS RDS를 반복 조회하며 큰 결과 집합을 받거나, CDC·로그를 클라우드 간 상시 전송하는 구성임.

**비용 원인:** AWS에서 나가는 DB 응답과 GCP에서 나가는 요청·쓰기 데이터를 각각의 Egress 조건으로 계산할 필요가 있음. 호출 횟수 자체보다 누적 전송량과 경로가 직접적인 비용 요인이며, NAT·VPN 등 경유 자원 비용도 합산 대상임.

**권장 대응:** 필요한 컬럼만 조회하고 캐시·배치·압축 적용 검토. 로그는 전송 전에 필터링·샘플링 권장. 지속적인 대량 DB 통신은 앱과 데이터의 동일 클라우드 배치 검토. 이전비·중단 위험·정합성·백업·운영 인력까지 포함한 총비용 비교 필요.

전용 연결도 회선 고정비와 전송 요금 검토 대상임. RDS Multi-AZ 복제 트래픽과 애플리케이션의 Cross-AZ 통신은 서로 다른 과금 조건이므로 구분 필요. [RDS 요금](https://aws.amazon.com/rds/pricing/), [GCP 네트워크 요금](https://cloud.google.com/vpc/network-pricing) 참조.

## Kubernetes의 과다 Requests와 유휴 노드

**케이스:** 평소 CPU 200m를 사용하는 Pod에 2000m를 요청하여, 실제 CPU가 남아 있는데도 노드가 추가되는 상황임.

**비용 원인:** 스케줄러는 실사용량보다 Requests를 기준으로 배치 가능 여부 판단. 과다 요청은 노드 증설을 유발하고, 남은 용량의 분산과 배치 제약은 노드 축소를 방해함.

**권장 대응:** CPU·메모리의 p95·피크·주기적 배치를 측정한 뒤 Requests 조정. VPA 권고와 OpenCost·Kubecost로 워크로드별 낭비 확인. Karpenter Consolidation으로 유휴 용량 통합 검토.

CPU Requests 변경 시 사용률 기반 HPA의 동작도 재검증 필요. 메모리 여유·지연 시간·OOM과 재배치 중단 영향을 함께 관찰할 필요가 있음. Graviton 전환은 arm64 이미지·네이티브 라이브러리 호환성과 실측 성능 검증 후 적용 권장. [Kubernetes 리소스 관리](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/), [EKS 비용 최적화](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt.html) 참조.

## Spot 절감과 고가용성의 트레이드오프

**케이스:** 핵심 서비스의 전체 Replica를 Spot 노드에 배치하고 PDB만으로 중단을 방어하려는 구성임.

**비용·장애 원인:** Spot 단가는 낮지만 회수 시 재시도·재처리와 서비스 장애 비용 발생 가능. PDB는 자발적 중단을 제한하는 장치이며 Spot 회수 방지 수단은 아님.

**권장 대응:** 중단 가능한 Stateless·배치부터 적용. 핵심 서비스의 최소 용량은 On-Demand 등으로 확보하고, Spot은 인스턴스 유형·AZ 분산과 Replica 확보를 병행하는 설계 검토. 중단 감지·Graceful Shutdown·재시도·체크포인트와 대체 용량 확보 절차 검증 필요.

Replica와 AZ 분산은 추가 비용을 수반하므로 허용 중단 시간과 복구 목표 기준으로 비율 결정 필요. [Kubernetes 중단 및 PDB](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/) 참조.

## 함께 점검할 기존 비용 항목

- **개발 환경 상시 실행:** 비업무 시간 종료 자동화 검토. 종료 후에도 EBS·할당 유지 EIP 등 잔여 비용 확인 필요.
- **로그·백업 누적:** 감사·복구 요건에 맞춘 Retention과 S3 Lifecycle 적용. 이전 버전·미완료 Multipart Upload·미사용 볼륨·Snapshot 점검 필요. 최소 보관 기간·조회료·복구 시간과 실제 복구 가능성 검증 필요.
- **낮은 CDN 캐시 적중률:** 불필요한 Cache Key 제거와 압축 검토. 개인정보·인증 응답의 캐시 안전성 검증 필요.
- **복잡한 VPC 연결:** Peering의 비전이성, Transit Gateway의 Attachment·처리비, Endpoint 중앙화 비용을 운영 복잡도와 함께 비교 필요.
- **IPv6 전환:** 상대 서비스·앱·DNS의 IPv6 지원 시 Egress-only Internet Gateway 경로 검토. NAT 처리비 절감과 외부 데이터 전송비는 별개임.

## 변경 전후 검증

Cost Explorer의 서비스·Usage Type, 활성화한 비용 할당 태그와 Cost Category로 비용 소유자 및 상위 지출 확인. CloudWatch·VPC Flow Logs로 사용량과 경로를 대조하되 로그 수집 비용도 관리 필요.

Budgets·Cost Anomaly Detection으로 이상 징후를 감시하고, 한 번에 한 항목씩 변경 후 **요청당 비용·p95 지연·오류율·복구 시간** 비교 권장. Rightsizing 후 Savings Plans·RI 약정 검토. [AWS Well-Architected 비용 최적화](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html) 기준의 지속적인 재평가 필요.

## 출처

박정빈·안다영·안진모·이준용·임정환, 『요즘 개발자를 위한 AWS 비용 최적화』, 길벗, 2026, ISBN 979-11-407-2057-6.

[직접 작성한 티스토리 원문](https://luv-n-interest.tistory.com/1674)을 바탕으로 운영 케이스와 권장 대응을 재구성함.
