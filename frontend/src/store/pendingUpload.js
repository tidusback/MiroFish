/**
 * 临时存储待上传的文件和需求
 * 用于首页点击启动引擎后立即跳转，在Process页面再进行API调用
 */
import { reactive } from 'vue'

const state = reactive({
  files: [],
  simulationRequirement: '',
  isPending: false,
  // News / reliable sources
  newsUrls: '',      // newline-separated article URLs
  rssFeeds: '',      // newline-separated RSS feed URLs
  insiderSources: [] // [{label, content}]
})

export function setPendingUpload(files, requirement, newsUrls = '', rssFeeds = '', insiderSources = []) {
  state.files = files
  state.simulationRequirement = requirement
  state.isPending = true
  state.newsUrls = newsUrls
  state.rssFeeds = rssFeeds
  state.insiderSources = insiderSources
}

export function getPendingUpload() {
  return {
    files: state.files,
    simulationRequirement: state.simulationRequirement,
    isPending: state.isPending,
    newsUrls: state.newsUrls,
    rssFeeds: state.rssFeeds,
    insiderSources: state.insiderSources
  }
}

export function clearPendingUpload() {
  state.files = []
  state.simulationRequirement = ''
  state.isPending = false
  state.newsUrls = ''
  state.rssFeeds = ''
  state.insiderSources = []
}

export default state
