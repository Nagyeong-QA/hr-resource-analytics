# HR Resource Analytics
조직·프로젝트별 타임시트 데이터를 기반으로
투입공수, 가동률, OT, 인력 배분 현황을 분석하는 HR Resource Analytics 프로젝트 

## Project Overview
- 개인별 Excel에 분산된 타임시트 데이터를 통합 관리
- 가동률·투입공수·OT 등 조직 운영 지표 정의
- Python·SQL 기반 데이터 저장 및 분석 구조 설계
- 조직·프로젝트별 Resource Dashboard 구현
- 인력 배분 및 충원 검토를 위한 분석 정보 제공

## Problem
- 개인별 Excel 관리로 조직 전체 데이터를 통합 분석하기 어려움
- 입력 오류 및 중복 배정 확인에 반복적인 수작업 발생
- 단순 가동률만으로는 실제 조직 상황을 정확히 판단하기 어려움

## Key Features
- Timesheet 데이터 수집 및 정제
- 잘못된 시간 입력 및 중복 배정 검증
- 조직·프로젝트별 투입공수 분석
- Utilization / Overtime / Project Allocation 산출
- Dashboard 기반 조직 리소스 현황 시각화
- 프로젝트 중복·일반업무 등 운영 조건을 반영한 분석

## Results
- 주 1~2회 발생하던 수기 수정 → 0건
- 주간 데이터 집계·검증 약 2시간 → 약 1분
- 조직별 인력 배분 및 충원 검토 자료로 활용

## Tech Stack
- Python
- SQL
- Excel / VBA

## Note
- 조직 이동 및 프로젝트 코드 변경으로 인한 집계 오류를 방지하기 위해 실제 운영 환경에서는 조직 이력과 프로젝트 Alias 기준도 함께 관리
