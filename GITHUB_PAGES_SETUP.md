# GitHub Pages 설정

현재 파일은 `https://powerpower2005.github.io/`를 기준으로 준비했습니다.
예시 글, 가상 프로젝트, 예시 공유 이미지는 제거했습니다.
프로필 이름은 Sirius이며 그림은 기본 SVG를 유지했습니다. 댓글은 giscus의 Announcements 카테고리에 연결했고, 통계는 토큰을 입력하면 켜집니다.
글에 `image`를 지정하면 해당 이미지를 공유 미리보기에 사용합니다. 기본 예시 이미지는 없습니다.

## 저장소 선택

- 기본 주소: `powerpower2005/powerpower2005.github.io`, `baseurl: ""`.
- portal 주소: `powerpower2005/portal`, `baseurl: "/portal"`.
- 두 경우 모두 `_config.yml`의 `url`은 `https://powerpower2005.github.io`입니다.
- 배포 워크플로는 Pages 설정에서 경로를 읽어 Jekyll에 전달합니다.

기존 기본 주소 저장소는 `powerpower2005/abcd`로 이름이 변경되었습니다.
기존 파일은 해당 저장소에 그대로 있습니다. 이번 블로그는 비어 있던 `portal` 저장소를
`powerpower2005.github.io`로 변경해서 사용합니다.

## 필수 설정

1. 저장소의 기본 브랜치를 `main`으로 사용합니다. `.github/workflows/deploy.yml`은 `main` 푸시에 배포됩니다.
2. **Settings → Pages → Build and deployment → Source → GitHub Actions**를 선택합니다.
   별도 Jekyll 워크플로를 추가하지 마세요. 이 저장소에 배포 워크플로가 있습니다.
3. **Settings → Actions → General**에서 이 워크플로가 사용하는 Actions가 허용되어 있는지 확인합니다.
   기본 정책이면 추가 변경이 필요 없습니다. 워크플로가 필요한 권한을 직접 선언합니다.
   자동 번역본 저장에는 `contents: write`, 배포에는 `pages: write`와 `id-token: write`를 사용합니다.
4. 파일을 `main`에 올린 뒤 **Actions → 블로그 배포**를 확인합니다.
   수동 재실행은 **Run workflow**로 할 수 있습니다.
5. 빌드와 배포가 모두 성공한 뒤 홈페이지, `/blog/`, `/projects/`, `/search/`를 확인합니다.
   글이 없는 초기 상태에는 검색 결과와 번역 글이 없는 것이 정상입니다.

공식 안내: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

## 댓글 설정 (선택)

1. **Settings → General → Features → Discussions**를 켭니다.
2. https://github.com/apps/giscus 에서 해당 저장소에 giscus 앱을 설치합니다.
3. https://giscus.app/ko 에 저장소 이름을 입력하고 카테고리를 선택합니다.
   카테고리는 Announcements 유형을 권장합니다.
4. 생성된 코드에서 아래 값을 `_config.yml`에 옮깁니다.

```yaml
giscus:
  repo: "powerpower2005/powerpower2005.github.io"
  repo_id: "data-repo-id 값"
  category: "선택한 카테고리 이름"
  category_id: "data-category-id 값"
```

이 사이트의 JavaScript가 글 파일명을 기준으로 댓글을 연결합니다.
생성된 script를 템플릿에 추가할 필요는 없습니다.
댓글 작성 후 아래 댓글창과 문단 댓글 표시를 각각 확인하세요.
문단 표시는 Discussion 이벤트로 재배포된 후 반영됩니다.

## 글쓰기 및 프로필

- https://app.pagescms.org 에서 GitHub로 로그인하고 저장소의 `main` 브랜치를 선택합니다.
  `.pages.yml`에 글, 번역, 프로젝트, 링크 메뉴가 준비되어 있습니다.
- 이름과 소개: `_config.yml`의 `title`, `author.name`, `author.bio`.
- 프로필 그림: `assets/img/avatar.svg`를 교체하거나 `author.avatar` 경로를 바꿉니다.
- 링크: `_data/links.yml`. 프로젝트: `_data/projects.yml`.
- 첫 글은 `_posts/YYYY-MM-DD-slug.md`로 작성합니다. 자동 번역을 건너뛰려면 `translate: false`를 넣습니다.
- 제공된 `security-review.yml`은 매월 보안 점검 이슈를 생성합니다.
  필요하지 않으면 Actions에서 해당 워크플로를 비활성화하세요.

## 이름을 바꾸는 경우

블로그에 표시하는 이름이나 GitHub 프로필의 표시 이름을 바꿔도 주소는 그대로입니다.
GitHub 로그인 아이디를 바꾸면 기본 사이트용 저장소도 `새아이디.github.io`로 바꾸고,
`_config.yml`의 `url`, 링크, 프로젝트 저장소 주소, giscus의 `repo`, Git 원격 주소를 갱신합니다.
기존 Pages 주소의 자동 이동을 전제로 사용하지 마세요.

## 검증 범위

GitHub Actions에서 Jekyll 전체 빌드와 Pages 배포 성공을 확인했습니다.
실제 번역 모델 실행과 GitHub 댓글 연동도 첫 글과 댓글을 올린 뒤 확인하세요.
